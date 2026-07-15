"""Runtime Relation Service — walk static and database-bound ontology links."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from sqlalchemy import create_engine, text as sa_text
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.v2.object_type import ObjectType
    from app.models.v2.data_source import DataSource


class RuntimeRelationService:
    """Resolve relationships from local Link rows plus manual DB link bindings."""

    def __init__(self, db: Session):
        self.db = db

    def get_relations(
        self,
        ontology_id: str,
        object_type: "ObjectType",
        object_key: str,
        source_instance_id: str | None = None,
        relation_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return outgoing relationships for an object.

        Manual ontologies can expose both materialized graph links and virtual
        database-backed links.  Static links require an ObjectInstance id;
        dynamic links only require the source business key.
        """
        results: list[dict[str, Any]] = []
        if source_instance_id:
            results.extend(self._static_relations(ontology_id, source_instance_id, relation_type))
        results.extend(self._dynamic_relations(ontology_id, object_type, object_key, relation_type))
        return results

    # ── static links ───────────────────────────────────────

    def _static_relations(
        self,
        ontology_id: str,
        source_instance_id: str,
        relation_type: str | None = None,
    ) -> list[dict[str, Any]]:
        from app.models.v2.object_type import Link, LinkType, ObjectInstance, ObjectType

        query = self.db.query(Link).filter(
            Link.ontology_id == ontology_id,
            Link.source_instance_id == source_instance_id,
        )

        if relation_type:
            lt = self.db.query(LinkType).filter(
                LinkType.ontology_id == ontology_id,
                (LinkType.name_en == relation_type) | (LinkType.name_cn == relation_type) | (LinkType.id == relation_type),
            ).first()
            if lt:
                query = query.filter(Link.link_type_id == lt.id)
            else:
                return []

        links = query.all()
        results: list[dict[str, Any]] = []
        for link in links:
            target = self.db.query(ObjectInstance).filter(
                ObjectInstance.id == link.target_instance_id,
                ObjectInstance.ontology_id == ontology_id,
            ).first()
            if not target:
                continue
            target_type = self.db.query(ObjectType).filter(
                ObjectType.id == target.object_type_id,
                ObjectType.ontology_id == ontology_id,
            ).first()
            lt = self._link_type(link.link_type_id)
            results.append({
                "relation": _link_type_key(lt, link.link_type_id),
                "relation_label": lt.name_cn if lt else link.link_type_id,
                "source_kind": "static_link",
                "source_id": source_instance_id,
                "target_id": target.id,
                "target_key": target.name_en or target.name_cn or target.id,
                "target_label": target.name_cn,
                "target_type": target_type.name_cn if target_type else None,
                "target_type_key": target_type.name_en or target_type.id if target_type else None,
                "properties": link.properties or {},
                "confidence": float(link.confidence) if link.confidence else 1.0,
            })
        return results

    # ── dynamic DB link bindings ───────────────────────────

    def _dynamic_relations(
        self,
        ontology_id: str,
        object_type: "ObjectType",
        object_key: str,
        relation_type: str | None = None,
    ) -> list[dict[str, Any]]:
        from app.models.v2.manual_binding import ManualLinkBinding
        from app.models.v2.object_type import LinkType, ObjectType

        q = self.db.query(ManualLinkBinding).filter(
            ManualLinkBinding.ontology_id == ontology_id,
            ManualLinkBinding.source_object_type_id == object_type.id,
            ManualLinkBinding.is_active == True,  # noqa: E712
        )
        if relation_type:
            lt = self.db.query(LinkType).filter(
                LinkType.ontology_id == ontology_id,
                (LinkType.name_en == relation_type) | (LinkType.name_cn == relation_type) | (LinkType.id == relation_type),
            ).first()
            if not lt:
                return []
            q = q.filter(ManualLinkBinding.link_type_id == lt.id)

        bindings = q.all()
        results: list[dict[str, Any]] = []
        for binding in bindings:
            source = self._get_source(binding.data_source_id)
            if not source:
                continue
            config = source.db_config or {}
            dialect = config.get("db_type", "postgres")
            table = _fmt_table(binding.schema_name, binding.table_name, dialect)
            target_col = _quote(binding.target_key_column, dialect)
            select_cols = [f"{target_col} AS target_key"]
            prop_bindings = binding.property_bindings or {}
            for prop_name, col_name in prop_bindings.items():
                select_cols.append(f"{_quote(str(col_name), dialect)} AS {_quote(str(prop_name), dialect)}")
            where_sql, params = _where_sql(binding.relation_filters or {}, dialect)
            params["source_key"] = object_key
            sql = (
                f"SELECT {', '.join(select_cols)} FROM {table} "
                f"WHERE {_quote(binding.source_key_column, dialect)} = :source_key{where_sql} "
                f"LIMIT 500"
            )
            try:
                engine = _make_engine(source)
                with engine.connect() as conn:
                    rows = conn.execute(sa_text(sql), params).mappings().all()
            except Exception as exc:
                results.append({
                    "relation": binding.link_type_id,
                    "source_kind": "dynamic_binding",
                    "source_key": object_key,
                    "error": str(exc),
                })
                continue

            link_type = self._link_type(binding.link_type_id)
            target_type = self.db.query(ObjectType).filter(
                ObjectType.id == binding.target_object_type_id,
                ObjectType.ontology_id == ontology_id,
            ).first()
            for row in rows:
                target_key = row.get("target_key")
                props = {name: _json_value(row.get(name)) for name in prop_bindings.keys()}
                results.append({
                    "relation": _link_type_key(link_type, binding.link_type_id),
                    "relation_label": link_type.name_cn if link_type else binding.link_type_id,
                    "source_kind": "dynamic_binding",
                    "data_source_id": binding.data_source_id,
                    "table": _fmt_table_path(binding.schema_name, binding.table_name),
                    "source_type": object_type.name_cn,
                    "source_type_key": object_type.name_en or object_type.id,
                    "source_key": object_key,
                    "target_type": target_type.name_cn if target_type else None,
                    "target_type_key": target_type.name_en or target_type.id if target_type else None,
                    "target_key": str(target_key) if target_key is not None else None,
                    "target_label": str(target_key) if target_key is not None else None,
                    "properties": props,
                    "confidence": 1.0,
                })
        return results

    def _link_type(self, link_type_id: str):
        from app.models.v2.object_type import LinkType
        return self.db.query(LinkType).filter(LinkType.id == link_type_id).first()

    def _get_source(self, source_id: str | None):
        from app.models.v2.data_source import DataSource
        if not source_id:
            return None
        return self.db.query(DataSource).filter(DataSource.id == source_id).first()


# ── helpers ────────────────────────────────────────────────

import re as _re
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import quote_plus

_IDENT = _re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote(value: str, dialect: str) -> str:
    if not _IDENT.match(value):
        raise ValueError(f"Unsafe identifier: {value!r}")
    q = "`" if dialect == "mysql" else '"'
    return f"{q}{value}{q}"


def _fmt_table(schema: str | None, table: str, dialect: str = "postgres") -> str:
    q = "`" if dialect == "mysql" else '"'
    t = f"{q}{table}{q}"
    if schema:
        return f"{q}{schema}{q}.{t}"
    return t


def _fmt_table_path(schema: str | None, table: str | None) -> str:
    if schema and table:
        return f"{schema}.{table}"
    return table or "?"


def _make_engine(source: "DataSource"):
    config = source.db_config or {}
    db_type = config.get("db_type", "postgres")
    host = config.get("host", "localhost")
    port = str(config.get("port", 5432 if db_type == "postgres" else 3306))
    user = quote_plus(str(config.get("user", "")))
    pwd = quote_plus(str(config.get("password", "")))
    db = quote_plus(str(config.get("database", "")))
    if db_type == "postgres":
        url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
    else:
        url = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}"
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


def _where_sql(filters: list[dict[str, Any]] | dict[str, Any], dialect: str) -> tuple[str, dict[str, Any]]:
    if not filters:
        return "", {}
    items = [{"column": k, "op": "eq", "value": v} for k, v in filters.items()] if isinstance(filters, dict) else filters
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for i, item in enumerate(items):
        col = item.get("column")
        if not col:
            raise ValueError("relation filter requires column")
        op = item.get("op", "eq")
        key = f"f{i}"
        quoted = _quote(str(col), dialect)
        if op == "eq":
            clauses.append(f"{quoted} = :{key}")
            params[key] = item.get("value")
        elif op == "neq":
            clauses.append(f"{quoted} <> :{key}")
            params[key] = item.get("value")
        elif op == "like":
            clauses.append(f"{quoted} LIKE :{key}")
            params[key] = item.get("value")
        elif op in {"gt", "gte", "lt", "lte"}:
            symbol = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]
            clauses.append(f"{quoted} {symbol} :{key}")
            params[key] = item.get("value")
        else:
            raise ValueError(f"Unsupported relation filter op: {op!r}")
    return " AND " + " AND ".join(clauses), params


def _link_type_key(link_type, fallback: str) -> str:
    if link_type:
        return link_type.name_en or link_type.name_cn or link_type.id
    return fallback


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value
