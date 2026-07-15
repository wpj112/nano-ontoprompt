"""Runtime Object Service — semantic object read through ontology field bindings."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from sqlalchemy import create_engine, text as sa_text
from sqlalchemy.orm import Session

from app.services.v2.transform import execute as tx_execute, TransformError

if TYPE_CHECKING:
    from app.models.v2.data_source import DataSource
    from app.models.v2.manual_binding import ManualFieldBinding
    from app.models.v2.object_type import ObjectType


class RuntimeObjectService:
    """Resolve ontology objects via field bindings to external data sources."""

    def __init__(self, db: Session):
        self.db = db

    # ── public API ──────────────────────────────────────────

    def get_object(
        self,
        ontology_id: str,
        object_type: "ObjectType",
        object_key: str,
    ) -> dict[str, Any]:
        """Read a single object with all bound properties resolved."""
        from app.models.v2.manual_binding import ManualFieldBinding

        bindings = (
            self.db.query(ManualFieldBinding)
            .filter(
                ManualFieldBinding.ontology_id == ontology_id,
                ManualFieldBinding.object_type_id == object_type.id,
            )
            .all()
        )

        properties: dict[str, Any] = {}
        sources: dict[str, Any] = {}

        for b in bindings:
            try:
                value = self._read_bound_value(b, object_key)
            except Exception as exc:
                value = None
                sources[b.property_name] = {"error": str(exc)}
            else:
                properties[b.property_name] = value
                if b.data_source_id:
                    sources[b.property_name] = {
                        "data_source_id": b.data_source_id,
                        "table": _fmt_table_path(b.schema_name, b.table_name),
                        "column": b.column_name,
                        "pk_column": b.primary_key_column,
                    }

        return {
            "id": object_key,
            "type_key": object_type.name_en or object_type.name_cn,
            "type_label": object_type.name_cn,
            "properties": properties,
            "_sources": sources,
        }

    def list_object_keys(
        self,
        ontology_id: str,
        object_type: "ObjectType",
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """List object business keys for a type, by querying bound tables.

        Returns the primary-key column values from the first bound table.
        If *fields* is given, also returns those column values.
        """
        from app.models.v2.manual_binding import ManualFieldBinding
        from app.models.v2.data_source import DataSource

        binding = (
            self.db.query(ManualFieldBinding)
            .filter(
                ManualFieldBinding.ontology_id == ontology_id,
                ManualFieldBinding.object_type_id == object_type.id,
            )
            .first()
        )
        if not binding or not binding.primary_key_column:
            return []

        source = self._get_source(binding.data_source_id)
        config = source.db_config or {}
        dialect = config.get("db_type", "postgres")

        # safe columns: pk + requested fields
        pk = _safe_ident(binding.primary_key_column)
        cols = [pk]
        if fields:
            for f in fields:
                cols.append(_safe_ident(f))

        table = _fmt_table(binding.schema_name, binding.table_name, dialect)
        try:
            engine = _make_engine(source)
            with engine.connect() as conn:
                sql = f"SELECT {', '.join(cols)} FROM {table} LIMIT 100"
                rows = conn.execute(sa_text(sql)).mappings().all()
                return [dict(r) for r in rows]
        except Exception:
            return []

    def query_objects(
        self,
        ontology_id: str,
        object_type: "ObjectType",
        *,
        filter: dict[str, Any] | None = None,
        sort: list[dict[str, Any]] | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Query virtual objects by resolved ontology properties.

        This intentionally resolves each candidate object through field bindings first,
        then applies semantic property filters in Python.  It is slower than SQL
        pushdown, but keeps the Runtime API independent from raw database columns.
        """
        from app.models.v2.manual_binding import ManualFieldBinding

        bindings = (
            self.db.query(ManualFieldBinding)
            .filter(
                ManualFieldBinding.ontology_id == ontology_id,
                ManualFieldBinding.object_type_id == object_type.id,
            )
            .all()
        )
        if not bindings:
            return []

        keys = self.list_object_keys(ontology_id, object_type)
        pk_col = bindings[0].primary_key_column or "id"
        results: list[dict[str, Any]] = []
        seen: set[str] = set()

        for row in keys[:500]:
            pk_val = row.get(pk_col) or row.get(pk_col.lower())
            if pk_val is None:
                pk_val = next((v for v in row.values() if v is not None), None)
            if pk_val is None or str(pk_val) in seen:
                continue
            seen.add(str(pk_val))
            obj = self.get_object(ontology_id, object_type, str(pk_val))
            props = obj.get("properties", {})
            if _matches_filter(props, filter or {}):
                results.append(obj)

        for spec in reversed(sort or []):
            field = spec.get("field")
            if not field:
                continue
            reverse = str(spec.get("direction", "asc")).lower() == "desc"
            results.sort(key=lambda item: _sort_key(item.get("properties", {}).get(field)), reverse=reverse)

        return results[: int(limit)]

    # ── internals ──────────────────────────────────────────

    def _read_bound_value(self, binding: "ManualFieldBinding", object_key: str) -> Any:
        if not binding.data_source_id or not binding.primary_key_column:
            return None
        source = self._get_source(binding.data_source_id)
        return tx_execute(binding, object_key, source)

    def _get_source(self, source_id: str | None) -> "DataSource":
        from app.models.v2.data_source import DataSource
        if not source_id:
            raise RuntimeError("No data_source_id")
        s = self.db.query(DataSource).filter(DataSource.id == source_id).first()
        if not s:
            raise RuntimeError(f"DataSource {source_id} not found")
        return s


# ── helpers ────────────────────────────────────────────────

import re as _re
_IDENT = _re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

def _safe_ident(value: str) -> str:
    if not _IDENT.match(value):
        raise ValueError(f"Unsafe identifier: {value!r}")
    return value

def _fmt_table(schema: str | None, table: str, dialect: str = "postgres") -> str:
    q = '"' if dialect in ("postgres", "postgresql") else "`"
    t = f'{q}{table}{q}'
    if schema:
        t = f'{q}{schema}{q}.{t}'
    return t

def _fmt_table_path(schema: str | None, table: str | None) -> str:
    if schema and table:
        return f"{schema}.{table}"
    return table or "?"

def _make_engine(source: "DataSource"):
    from urllib.parse import quote_plus
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


def _matches_filter(props: dict[str, Any], filters: dict[str, Any]) -> bool:
    for field, expected in filters.items():
        actual = props.get(field)
        if isinstance(expected, dict):
            op = expected.get("op", "eq")
            value = expected.get("value")
        else:
            op = "eq"
            value = expected
        if not _compare(actual, op, value):
            return False
    return True


def _compare(actual: Any, op: str, expected: Any) -> bool:
    if op == "eq":
        return str(actual) == str(expected)
    if op == "neq":
        return str(actual) != str(expected)
    if op == "contains":
        return str(expected) in str(actual)
    if op == "in":
        return actual in (expected or []) or str(actual) in {str(v) for v in (expected or [])}
    if op in {"gt", "gte", "lt", "lte"}:
        try:
            left = float(actual)
            right = float(expected)
        except (TypeError, ValueError):
            left = str(actual)
            right = str(expected)
        if op == "gt":
            return left > right
        if op == "gte":
            return left >= right
        if op == "lt":
            return left < right
        if op == "lte":
            return left <= right
    return False


def _sort_key(value: Any):
    if value is None:
        return (1, "")
    try:
        return (0, float(value))
    except (TypeError, ValueError):
        return (0, str(value))
