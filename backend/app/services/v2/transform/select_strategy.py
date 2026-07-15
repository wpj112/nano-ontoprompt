"""Safe SQL building for different data-selection strategies.

Every table/column/schema name is validated against a whitelist regex before
being quoted.  No raw SQL fragments are ever interpolated.
"""

from __future__ import annotations

import re
from typing import Any

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_AGGREGATES = frozenset({"max", "min", "avg", "sum", "count"})


class SelectError(RuntimeError):
    pass


def _quote(value: str, dialect: str) -> str:
    if not _IDENT.match(value):
        raise SelectError(f"Unsafe identifier: {value!r}")
    q = "`" if dialect == "mysql" else '"'
    return f"{q}{value}{q}"


def _qualified_table(schema_name: str | None, table_name: str, dialect: str) -> str:
    t = _quote(table_name, dialect)
    if schema_name:
        return f"{_quote(schema_name, dialect)}.{t}"
    return t



def _extra_where(where: list[dict[str, Any]] | dict[str, Any] | None, dialect: str, params: dict[str, Any]) -> str:
    if not where:
        return ""
    items: list[dict[str, Any]]
    if isinstance(where, dict):
        items = [{"column": k, "op": "eq", "value": v} for k, v in where.items()]
    else:
        items = where
    clauses: list[str] = []
    for i, item in enumerate(items):
        col = item.get("column")
        if not col:
            raise SelectError("where item requires 'column'")
        op = item.get("op", "eq")
        key = f"w{i}"
        quoted = _quote(str(col), dialect)
        if op == "eq":
            clauses.append(f"{quoted} = :{key}")
            params[key] = item.get("value")
        elif op == "neq":
            clauses.append(f"{quoted} <> :{key}")
            params[key] = item.get("value")
        elif op in {"gt", "gte", "lt", "lte"}:
            symbol = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]
            clauses.append(f"{quoted} {symbol} :{key}")
            params[key] = item.get("value")
        elif op == "like":
            clauses.append(f"{quoted} LIKE :{key}")
            params[key] = item.get("value")
        elif op == "in":
            vals = item.get("value") or []
            if not isinstance(vals, list) or not vals:
                raise SelectError("where op=in requires non-empty list value")
            placeholders = []
            for j, val in enumerate(vals):
                in_key = f"{key}_{j}"
                placeholders.append(f":{in_key}")
                params[in_key] = val
            clauses.append(f"{quoted} IN ({', '.join(placeholders)})")
        else:
            raise SelectError(f"Unsupported where op: {op!r}")
    return " AND " + " AND ".join(clauses)

def build_sql(
    *,
    mode: str,
    column: str | None = None,
    columns: list[str] | None = None,
    value_column: str | None = None,
    order_by: str | None = None,
    op: str | None = None,
    dialect: str = "postgres",
    schema_name: str | None = None,
    table_name: str = "",
    pk_column: str = "",
    limit_rows: int | None = None,
    where: list[dict[str, Any]] | dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return ``(parameterised_sql, bind_params)`` for a selection mode.

    Supported *mode* values
    -----------------------
    ``value`` — single-column, single-row (default / backward-compatible)::

        SELECT col FROM schema.table WHERE pk = :pk LIMIT 1

    ``columns`` — multiple columns returned as a dict::

        SELECT c1, c2 FROM schema.table WHERE pk = :pk LIMIT 1

    ``aggregate`` — ``op`` is one of max/min/avg/sum/count::

        SELECT {op}(col) FROM schema.table WHERE pk LIKE :pk ...

    ``latest`` — newest row ordered by *order_by*::

        SELECT col FROM schema.table WHERE pk LIKE :pk
        ORDER BY order_by DESC LIMIT 1

    ``earliest`` — oldest row::

        SELECT col FROM schema.table WHERE pk LIKE :pk
        ORDER BY order_by ASC LIMIT 1

    ``count`` — count rows::

        SELECT COUNT(*) FROM schema.table WHERE pk LIKE :pk

    Returns a ``(sql, params)`` tuple where *sql* uses ``:param``-style
    placeholders and *params* is a dict of named bind values.
    """
    table = _qualified_table(schema_name, table_name, dialect)
    params: dict[str, Any] = {"pk": ""}  # placeholder – caller fills this
    extra = _extra_where(where, dialect, params)

    if mode == "value":
        if not column:
            raise SelectError("mode=value requires 'column'")
        sql = f"SELECT {_quote(column, dialect)} AS value FROM {table} WHERE {_quote(pk_column, dialect)} = :pk{extra} LIMIT 1"

    elif mode == "columns":
        if not columns:
            raise SelectError("mode=columns requires 'columns'")
        quoted = [_quote(c, dialect) for c in columns]
        sql = f"SELECT {', '.join(quoted)} FROM {table} WHERE {_quote(pk_column, dialect)} = :pk{extra} LIMIT 1"

    elif mode == "aggregate":
        if not op or op not in _AGGREGATES:
            raise SelectError(f"mode=aggregate requires 'op' be one of {sorted(_AGGREGATES)}")
        col = column or "*"
        if col != "*":
            col = _quote(col, dialect)
        sql = f"SELECT {op.upper()}({col}) AS value FROM {table} WHERE {_quote(pk_column, dialect)} LIKE :pk{extra}"

    elif mode in ("latest", "earliest"):
        if not value_column:
            raise SelectError(f"mode={mode} requires 'value_column'")
        if not order_by:
            raise SelectError(f"mode={mode} requires 'order_by'")
        direction = "DESC" if mode == "latest" else "ASC"
        vc = _quote(value_column, dialect)
        ob = _quote(order_by, dialect)
        pk = _quote(pk_column, dialect)
        limit = ""
        if limit_rows is not None and limit_rows > 0:
            limit = f" LIMIT {int(limit_rows)}"
        sql = (
            f"SELECT {vc} AS value FROM {table}"
            f" WHERE {pk} LIKE :pk{extra}"
            f" ORDER BY {ob} {direction}"
            f"{limit} LIMIT 1"
        )

    elif mode == "count":
        col = _quote(column, dialect) if column else "*"
        sql = f"SELECT COUNT({col}) AS value FROM {table} WHERE {_quote(pk_column, dialect)} LIKE :pk{extra}"

    else:
        raise SelectError(f"Unknown select mode: {mode!r}")

    return sql, params
