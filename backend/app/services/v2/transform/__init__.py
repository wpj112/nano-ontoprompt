"""Transform Engine — structured value selection + pipeline transformation.

Public API
----------
- :func:`execute` — run a binding's full transform (select → pipeline → cast)
- :class:`TransformError` — raised for invalid config / unsupported ops
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.v2.data_source import DataSource
    from app.models.v2.manual_binding import ManualFieldBinding
    from sqlalchemy import Engine

from .pipeline import run_pipeline, PipelineError
from .select_strategy import build_sql, SelectError


class TransformError(RuntimeError):
    pass


# ── type casting ────────────────────────────────────────────

def _cast_value(value: Any, value_type: str) -> Any:
    if value is None:
        return None
    if value_type == "number":
        try:
            return float(value) if not isinstance(value, (int, float, Decimal)) else value
        except (ValueError, TypeError):
            return None
    if value_type == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("1", "true", "yes", "y", "on")
        if isinstance(value, (int, float)):
            return value != 0
        return bool(value)
    if value_type == "datetime":
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return str(value)
    if value_type == "json":
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value
    return str(value) if value is not None else None


# ── data source connection ──────────────────────────────────

def _get_engine(source: "DataSource") -> "Engine":
    from urllib.parse import quote_plus
    from sqlalchemy import create_engine

    config = source.db_config or {}
    db_type = config.get("db_type", "postgres")
    host = config.get("host", "localhost")
    port = str(config.get("port", 5432 if db_type == "postgres" else 3306))
    user = quote_plus(str(config.get("user", "")))
    pwd = quote_plus(str(config.get("password", "")))
    db = quote_plus(str(config.get("database", "")))

    if db_type == "postgres":
        url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}"
    elif db_type == "mysql":
        url = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}"
    else:
        raise TransformError(f"Unsupported db_type: {db_type}")

    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})


def _dialect(source: "DataSource") -> str:
    config = source.db_config or {}
    return config.get("db_type", "postgres")


# ── main entry ──────────────────────────────────────────────

def execute(
    binding: "ManualFieldBinding",
    object_key: str,
    source: "DataSource",
) -> Any:
    """Execute the full transform chain for a single field binding.

    1. Parse ``binding.transform_expression`` as JSON config
    2. If no ``select`` key → fall back to legacy single-column mode
    3. Build safe SQL via :func:`build_sql`
    4. Execute query against the data source
    5. Run :func:`run_pipeline` on result
    6. Cast to ``binding.value_type``

    Returns the transformed value, or ``None`` on empty result.
    """
    config = _parse_config(binding.transform_expression)

    select_cfg = config.get("select")
    pipeline_cfg: list[dict] = config.get("pipeline", [])

    if select_cfg is None:
        return _legacy_read(binding, object_key, source, pipeline_cfg)

    mode = select_cfg.get("mode", "value")
    dialect_name = _dialect(source)

    sql, params = build_sql(
        mode=mode,
        column=select_cfg.get("column"),
        columns=select_cfg.get("columns"),
        value_column=select_cfg.get("value_column"),
        order_by=select_cfg.get("order_by"),
        op=select_cfg.get("op"),
        dialect=dialect_name,
        schema_name=binding.schema_name,
        table_name=binding.table_name,
        pk_column=binding.primary_key_column or "",
        limit_rows=select_cfg.get("limit"),
        where=select_cfg.get("where"),
    )
    # LIKE for aggregate/count modes, exact match for value/columns
    if mode in ("value", "columns"):
        params["pk"] = object_key
    else:
        params["pk"] = f"%{object_key}%"

    engine = _get_engine(source)
    try:
        with engine.connect() as conn:
            from sqlalchemy import text as sa_text
            if mode == "columns":
                row = conn.execute(sa_text(sql), params).fetchone()
                result: Any = dict(zip(row.keys(), row)) if row else {}
            else:
                row = conn.execute(sa_text(sql), params).fetchone()
                result = row[0] if row else None
    except Exception as exc:
        raise TransformError(f"SQL execution failed [{binding.property_name}]: {exc}") from exc

    if pipeline_cfg:
        result = run_pipeline(result, pipeline_cfg)

    return _cast_value(result, binding.value_type)


# ── internals ───────────────────────────────────────────────

def _parse_config(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        cfg = json.loads(raw)
        if not isinstance(cfg, dict):
            raise TransformError("transform_expression must be a JSON object")
        return cfg
    except json.JSONDecodeError as exc:
        raise TransformError(f"Invalid transform_expression JSON: {exc}") from exc


def _legacy_read(
    binding: "ManualFieldBinding",
    object_key: str,
    source: "DataSource",
    pipeline_cfg: list[dict],
) -> Any:
    config = source.db_config or {}
    dialect_name = config.get("db_type", "postgres")
    sql, params = build_sql(
        mode="value",
        column=binding.column_name,
        dialect=dialect_name,
        schema_name=binding.schema_name,
        table_name=binding.table_name,
        pk_column=binding.primary_key_column or "",
        where={},
    )
    params["pk"] = object_key

    engine = _get_engine(source)
    try:
        with engine.connect() as conn:
            from sqlalchemy import text as sa_text
            row = conn.execute(sa_text(sql), params).fetchone()
            result = row[0] if row else None
    except Exception as exc:
        raise TransformError(f"SQL execution failed [{binding.property_name}]: {exc}") from exc

    if pipeline_cfg:
        result = run_pipeline(result, pipeline_cfg)

    return _cast_value(result, binding.value_type)
