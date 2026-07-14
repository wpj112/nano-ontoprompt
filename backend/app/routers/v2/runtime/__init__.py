"""External runtime API boundary for published manual ontologies."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import re
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.object_action import ObjectAction
from app.models.object_rule import ObjectRule
from app.models.ontology import OntologyProject
from app.models.v2.data_source import DataSource
from app.models.v2.manual_binding import ManualFieldBinding
from app.models.v2.object_type import LinkType, ObjectType

router = APIRouter(dependencies=[Depends(get_current_user)])
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _get_runtime_ontology(ontology_id: str, db: Session) -> OntologyProject:
    ontology = db.query(OntologyProject).filter(OntologyProject.id == ontology_id).first()
    if not ontology:
        raise HTTPException(404, "Ontology not found")
    if ontology.build_mode != "manual":
        raise HTTPException(409, "Runtime API only supports build_mode=manual ontologies")
    return ontology


def _resolve_object_type(ontology_id: str, type_key: str, db: Session) -> ObjectType:
    item = db.query(ObjectType).filter(ObjectType.ontology_id == ontology_id, ObjectType.id == type_key).first()
    if item:
        return item
    item = db.query(ObjectType).filter(
        ObjectType.ontology_id == ontology_id,
        (ObjectType.name_en == type_key) | (ObjectType.name_cn == type_key),
    ).first()
    if not item:
        raise HTTPException(404, "ObjectType not found")
    return item


def _quote_identifier(value: str, dialect: str) -> str:
    if not value or not _IDENTIFIER_RE.match(value):
        raise HTTPException(400, f"Unsafe SQL identifier: {value}")
    quote = "`" if dialect == "mysql" else '"'
    return f"{quote}{value}{quote}"


def _qualified_table(schema_name: str | None, table_name: str, dialect: str) -> str:
    table = _quote_identifier(table_name, dialect)
    if schema_name:
        return f"{_quote_identifier(schema_name, dialect)}.{table}"
    return table


def _connection_url(config: dict) -> str:
    db_type = config.get("db_type") or config.get("kind") or "mysql"
    host = config.get("host") or "localhost"
    port = config.get("port") or (5432 if db_type == "postgres" else 3306)
    user = quote_plus(str(config.get("user") or config.get("username") or ""))
    password = quote_plus(str(config.get("password") or ""))
    database = quote_plus(str(config.get("database") or ""))
    if db_type == "postgres":
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    if db_type == "mysql":
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    raise HTTPException(400, f"Unsupported runtime data source type: {db_type}")


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _cast_value(value, value_type: str):
    if value is None:
        return None
    try:
        if value_type == "number":
            return float(value)
        if value_type == "boolean":
            if isinstance(value, bool):
                return value
            return str(value).lower() in {"1", "true", "t", "yes", "y"}
        if value_type == "string":
            return str(value)
    except Exception:
        return _json_value(value)
    return _json_value(value)


def _read_bound_value(binding: ManualFieldBinding, object_key: str, db: Session):
    if not binding.data_source_id:
        raise HTTPException(400, f"Binding {binding.property_name} has no data_source_id")
    if not binding.primary_key_column:
        raise HTTPException(400, f"Binding {binding.property_name} has no primary_key_column")
    source = db.query(DataSource).filter(
        DataSource.id == binding.data_source_id,
        DataSource.ontology_id == binding.ontology_id,
    ).first()
    if not source:
        raise HTTPException(404, f"DataSource not found for binding {binding.property_name}")

    config = source.db_config or {}
    dialect = config.get("db_type") or "mysql"
    engine = create_engine(_connection_url(config), pool_pre_ping=True, connect_args={"connect_timeout": 10})
    table = _qualified_table(binding.schema_name, binding.table_name, dialect)
    column = _quote_identifier(binding.column_name, dialect)
    pk = _quote_identifier(binding.primary_key_column, dialect)
    query = text(f"SELECT {column} AS value FROM {table} WHERE {pk} = :object_key LIMIT 1")
    try:
        with engine.connect() as conn:
            row = conn.execute(query, {"object_key": object_key}).mappings().first()
    except Exception as exc:
        raise HTTPException(502, f"Runtime data read failed for {binding.property_name}: {exc}") from exc
    if row is None:
        return None
    return _cast_value(row["value"], binding.value_type)


@router.get("/ontologies/{ontology_id}/metadata")
def get_runtime_metadata(ontology_id: str, db: Session = Depends(get_db)):
    ontology = _get_runtime_ontology(ontology_id, db)
    object_types = db.query(ObjectType).filter(ObjectType.ontology_id == ontology_id).all()
    link_types = db.query(LinkType).filter(LinkType.ontology_id == ontology_id).all()
    rules = db.query(ObjectRule).filter(ObjectRule.ontology_id == ontology_id).all()
    actions = db.query(ObjectAction).filter(ObjectAction.ontology_id == ontology_id).all()
    bindings = db.query(ManualFieldBinding).filter(ManualFieldBinding.ontology_id == ontology_id).all()
    return {
        "data": {
            "id": ontology.id,
            "name": ontology.name,
            "version": ontology.version,
            "status": ontology.status,
            "object_types": [
                {"id": item.id, "name_cn": item.name_cn, "name_en": item.name_en, "property_schema": item.property_schema or {}}
                for item in object_types
            ],
            "link_types": [
                {"id": item.id, "name_cn": item.name_cn, "name_en": item.name_en, "source_object_type_id": item.source_object_type_id, "target_object_type_id": item.target_object_type_id}
                for item in link_types
            ],
            "rules": [{"id": item.id, "name_cn": item.name_cn} for item in rules],
            "actions": [{"id": item.id, "name_cn": item.name_cn} for item in actions],
            "field_bindings": [
                {
                    "id": item.id,
                    "object_type_id": item.object_type_id,
                    "property_name": item.property_name,
                    "data_source_id": item.data_source_id,
                    "schema_name": item.schema_name,
                    "table_name": item.table_name,
                    "column_name": item.column_name,
                    "primary_key_column": item.primary_key_column,
                    "value_type": item.value_type,
                    "direction": item.direction,
                    "read_only": item.read_only,
                }
                for item in bindings
            ],
        }
    }


@router.get("/ontologies/{ontology_id}/objects/{type_key}/{object_key}")
def get_runtime_object(ontology_id: str, type_key: str, object_key: str, db: Session = Depends(get_db)):
    _get_runtime_ontology(ontology_id, db)
    object_type = _resolve_object_type(ontology_id, type_key, db)
    bindings = db.query(ManualFieldBinding).filter(
        ManualFieldBinding.ontology_id == ontology_id,
        ManualFieldBinding.object_type_id == object_type.id,
    ).all()
    if not bindings:
        raise HTTPException(404, "No field bindings configured for this ObjectType")

    properties = {}
    sources = {}
    for binding in bindings:
        value = _read_bound_value(binding, object_key, db)
        properties[binding.property_name] = value
        sources[binding.property_name] = {
            "data_source_id": binding.data_source_id,
            "schema_name": binding.schema_name,
            "table_name": binding.table_name,
            "column_name": binding.column_name,
            "primary_key_column": binding.primary_key_column,
        }

    return {
        "data": {
            "id": object_key,
            "object_type": {
                "id": object_type.id,
                "name_cn": object_type.name_cn,
                "name_en": object_type.name_en,
            },
            "properties": properties,
            "sources": sources,
        }
    }


@router.post("/ontologies/{ontology_id}/actions/{action_id}/execute")
def execute_runtime_action(ontology_id: str, action_id: str, db: Session = Depends(get_db)):
    _get_runtime_ontology(ontology_id, db)
    action = db.query(ObjectAction).filter(ObjectAction.id == action_id, ObjectAction.ontology_id == ontology_id).first()
    if not action:
        raise HTTPException(404, "Action not found")
    raise HTTPException(501, "Runtime action executor is not implemented yet")
