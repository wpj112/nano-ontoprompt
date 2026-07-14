"""数据源 CRUD + saved-source browsing for manual field bindings."""
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_user
from app.models.v2.data_source import DataSource
import uuid

router = APIRouter(dependencies=[Depends(get_current_user)])
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DataSourceCreate(BaseModel):
    name: str
    db_config: dict = {}
    registered_table: Optional[str] = None


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    db_config: Optional[dict] = None
    registered_table: Optional[str] = None


def _serialize_source(s: DataSource) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "db_config": s.db_config,
        "registered_table": s.registered_table,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _get_source(ontology_id: str, source_id: str, db: Session) -> DataSource:
    ds = db.query(DataSource).filter(DataSource.id == source_id, DataSource.ontology_id == ontology_id).first()
    if not ds:
        raise HTTPException(404, "DataSource not found")
    return ds


def _validate_identifier(value: str, label: str = "identifier") -> str:
    if not value or not _IDENTIFIER_RE.match(value):
        raise HTTPException(400, f"Unsafe {label}: {value}")
    return value


def _get_conn(config: dict):
    db_type = config.get("db_type", "mysql")
    host = config.get("host", "localhost")
    port = int(config.get("port") or (5432 if db_type == "postgres" else 3306))
    user = config.get("user", "")
    password = config.get("password", "")
    database = config.get("database", "")
    if db_type == "mysql":
        import pymysql
        return pymysql.connect(
            host=host, port=port, user=user,
            password=password, database=database,
            charset="utf8mb4", connect_timeout=5,
        )
    if db_type == "postgres":
        import psycopg2
        return psycopg2.connect(
            host=host, port=port, user=user,
            password=password, dbname=database,
            connect_timeout=5,
        )
    raise HTTPException(400, f"Unsupported database type: {db_type}")


@router.get("/{ontology_id}/data-sources")
def list_sources(ontology_id: str, db: Session = Depends(get_db)):
    items = db.query(DataSource).filter(DataSource.ontology_id == ontology_id).order_by(DataSource.created_at.desc()).all()
    return [_serialize_source(s) for s in items]


@router.post("/{ontology_id}/data-sources", status_code=201)
def create_source(ontology_id: str, body: DataSourceCreate, db: Session = Depends(get_db)):
    ds = DataSource(
        id=str(uuid.uuid4()),
        ontology_id=ontology_id,
        name=body.name,
        db_config=body.db_config,
        registered_table=body.registered_table,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return _serialize_source(ds)


@router.put("/{ontology_id}/data-sources/{source_id}")
def update_source(ontology_id: str, source_id: str, body: DataSourceUpdate, db: Session = Depends(get_db)):
    ds = _get_source(ontology_id, source_id, db)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(ds, key, value)
    db.commit()
    db.refresh(ds)
    return _serialize_source(ds)


@router.post("/{ontology_id}/data-sources/{source_id}/test")
def test_source(ontology_id: str, source_id: str, db: Session = Depends(get_db)):
    ds = _get_source(ontology_id, source_id, db)
    try:
        conn = _get_conn(ds.db_config or {})
        conn.close()
        return {"ok": True, "message": f"Connected: {ds.name}"}
    except Exception as exc:
        return {"ok": False, "message": f"Connection failed: {exc}"}


@router.get("/{ontology_id}/data-sources/{source_id}/tables")
def list_source_tables(ontology_id: str, source_id: str, schema_name: str = "", db: Session = Depends(get_db)):
    ds = _get_source(ontology_id, source_id, db)
    config = ds.db_config or {}
    db_type = config.get("db_type", "mysql")
    try:
        conn = _get_conn(config)
        cur = conn.cursor()
        if db_type == "mysql":
            cur.execute("SHOW TABLES")
            tables = [row[0] for row in cur.fetchall()]
        else:
            schema = schema_name or "public"
            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = %s ORDER BY table_name",
                (schema,),
            )
            tables = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return {"data": {"source_id": source_id, "schema_name": schema_name or None, "tables": tables}}
    except Exception as exc:
        raise HTTPException(400, f"Failed to list tables: {exc}") from exc


@router.get("/{ontology_id}/data-sources/{source_id}/columns")
def list_source_columns(
    ontology_id: str,
    source_id: str,
    table_name: str,
    schema_name: str = "",
    db: Session = Depends(get_db),
):
    ds = _get_source(ontology_id, source_id, db)
    config = ds.db_config or {}
    db_type = config.get("db_type", "mysql")
    try:
        conn = _get_conn(config)
        cur = conn.cursor()
        if db_type == "mysql":
            table = _validate_identifier(table_name, "table name")
            cur.execute(f"DESCRIBE `{table}`")
            columns = [{"name": row[0], "type": row[1]} for row in cur.fetchall()]
        else:
            schema = schema_name or "public"
            cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
                (schema, table_name),
            )
            columns = [{"name": row[0], "type": row[1]} for row in cur.fetchall()]
        cur.close()
        conn.close()
        return {"data": {"source_id": source_id, "schema_name": schema_name or None, "table_name": table_name, "columns": columns}}
    except Exception as exc:
        raise HTTPException(400, f"Failed to list columns: {exc}") from exc


@router.delete("/{ontology_id}/data-sources/{source_id}", status_code=204)
def delete_source(ontology_id: str, source_id: str, db: Session = Depends(get_db)):
    ds = _get_source(ontology_id, source_id, db)
    db.delete(ds)
    db.commit()
