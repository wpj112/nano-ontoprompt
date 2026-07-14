"""Value transformation pipeline — structured, safe, non-eval value processing."""

from __future__ import annotations

from decimal import Decimal
from datetime import date, datetime
import re
from typing import Any


class PipelineError(RuntimeError):
    pass


_OPS: dict[str, Any] = {}

def _register(name: str):
    def deco(fn):
        _OPS[name] = fn
        return fn
    return deco


# ── string ops ──────────────────────────────────────────────

@_register("trim")
def _trim(value: Any, **_kw) -> str:
    return str(value).strip() if value is not None else ""

@_register("lower")
def _lower(value: Any, **_kw) -> str:
    return str(value).lower() if value is not None else ""

@_register("upper")
def _upper(value: Any, **_kw) -> str:
    return str(value).upper() if value is not None else ""

@_register("title")
def _title(value: Any, **_kw) -> str:
    return str(value).title() if value is not None else ""

@_register("replace")
def _replace(value: Any, src: str = "", dst: str = "", **_kw) -> str:
    return str(value).replace(src, dst) if value is not None else ""

@_register("substring")
def _substring(value: Any, start: int = 0, length: int | None = None, **_kw) -> str:
    s = str(value) if value is not None else ""
    if length is not None:
        return s[start:start + length]
    return s[start:]

@_register("split")
def _split(value: Any, delimiter: str = ",", index: int = 0, **_kw):
    parts = str(value).split(delimiter) if value is not None else []
    return parts[index] if 0 <= index < len(parts) else None

@_register("join")
def _join(value: Any, delimiter: str = ",", **_kw) -> str:
    if isinstance(value, (list, tuple)):
        return delimiter.join(str(v) for v in value)
    return str(value) if value is not None else ""

@_register("regex_replace")
def _regex_replace(value: Any, pattern: str = "", repl: str = "", **_kw) -> str:
    s = str(value) if value is not None else ""
    return re.sub(pattern, repl, s)

@_register("concat")
def _concat(value: Any, template: str = "", **_kw) -> str:
    if isinstance(value, dict):
        return template.format(**{k: (str(v) if v is not None else "") for k, v in value.items()})
    if template and value is not None:
        return template.replace("{value}", str(value))
    return str(value) if value is not None else ""

@_register("default")
def _default(value: Any, val: Any = None, **_kw) -> Any:
    if value is None or value == "":
        return val
    return value


# ── number ops ──────────────────────────────────────────────

@_register("to_number")
def _to_number(value: Any, **_kw) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        raise PipelineError(f"Cannot cast {value!r} to number")

@_register("to_string")
def _to_string(value: Any, **_kw) -> str:
    return str(value) if value is not None else ""

@_register("to_bool")
def _to_bool(value: Any, **_kw) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "y", "on")
    if isinstance(value, (int, float)):
        return value != 0
    return bool(value)

@_register("to_date")
def _to_date(value: Any, fmt: str = "%Y-%m-%d", **_kw):
    if value is None or value == "":
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    try:
        return datetime.strptime(str(value), fmt).date().isoformat()
    except ValueError:
        raise PipelineError(f"Cannot parse {value!r} as date with format {fmt}")

@_register("round")
def _round(value: Any, digits: int = 0, **_kw) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value), digits)
    except (ValueError, TypeError):
        raise PipelineError(f"Cannot round {value!r}")


# ── runner ──────────────────────────────────────────────────

def run_pipeline(value: Any, steps: list[dict]) -> Any:
    """Execute a list of pipeline operation steps.

    Each step is a dict with at least an ``op`` key.  Extra keys are passed as
    keyword arguments to the operation function.

    The first op receives the raw *value*; each subsequent op receives the
    return value of the previous op.
    """
    result = value
    for step in steps:
        op_name = step.get("op")
        if not op_name:
            raise PipelineError("Pipeline step missing 'op' key")
        fn = _OPS.get(op_name)
        if fn is None:
            supported = ", ".join(sorted(_OPS))
            raise PipelineError(f"Unknown pipeline op: {op_name!r}. Supported: {supported}")
        params = {k: v for k, v in step.items() if k != "op"}
        result = fn(result, **params)
    return result
