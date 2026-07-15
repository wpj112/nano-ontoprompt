"""Runtime Action Service — execute ontology actions."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


class RuntimeActionService:
    """Execute ObjectActions against ontology instances."""

    def __init__(self, db: Session):
        self.db = db

    def execute(
        self,
        ontology_id: str,
        action_key: str,
        *,
        subject_type_key: str | None = None,
        subject_id: str | None = None,
        input_data: dict[str, Any] | None = None,
        dry_run: bool = False,
        idempotency_key: str | None = None,
        orchestration_run_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute a single action.

        *action_key* can be the action's name_cn or id.
        If *dry_run* is True, only validate without side effects.
        """
        from datetime import datetime, timezone
        import uuid
        from app.models.ontology import OntologyProject  # noqa: F401 - register FK target in SQLAlchemy metadata
        from app.models.object_action import ObjectAction
        from app.models.v2.manual_binding import ManualRuntimeActionRun

        action = self.db.query(ObjectAction).filter(
            ObjectAction.ontology_id == ontology_id,
            (ObjectAction.name_cn == action_key) | (ObjectAction.id == action_key),
        ).first()
        if not action:
            return {"status": "error", "message": f"Action not found: {action_key}"}

        if idempotency_key:
            query = self.db.query(ManualRuntimeActionRun).filter(
                ManualRuntimeActionRun.ontology_id == ontology_id,
                ManualRuntimeActionRun.idempotency_key == idempotency_key,
            )
            if orchestration_run_id:
                query = query.filter(ManualRuntimeActionRun.orchestration_run_id == orchestration_run_id)
            else:
                query = query.filter(ManualRuntimeActionRun.orchestration_run_id.is_(None))
            existing = query.first()
            if existing:
                return {
                    "status": existing.status,
                    "run_id": existing.id,
                    "idempotency_key": idempotency_key,
                    "orchestration_run_id": existing.orchestration_run_id,
                    "replayed": True,
                    "result": existing.result_payload or {},
                    "error": existing.error,
                }

        if dry_run:
            return {
                "status": "dry_run",
                "action_key": action.name_cn,
                "action_id": action.id,
                "idempotency_key": idempotency_key,
                "orchestration_run_id": orchestration_run_id,
                "message": "Dry run - action would execute",
            }

        run = ManualRuntimeActionRun(
            id=str(uuid.uuid4()),
            ontology_id=ontology_id,
            action_key=action.name_cn or action.id,
            orchestration_run_id=orchestration_run_id,
            idempotency_key=idempotency_key,
            status="running",
            request_payload={
                "subject_type_key": subject_type_key,
                "subject_id": subject_id,
                "input": input_data or {},
                "dry_run": dry_run,
                "orchestration_run_id": orchestration_run_id,
            },
        )
        self.db.add(run)
        self.db.commit()

        # build execution context
        context: dict[str, Any] = {
            "action_name": action.name_cn,
            "action_id": action.id,
            "subject_type_key": subject_type_key,
            "subject_id": subject_id,
            "ontology_id": ontology_id,
            "orchestration_run_id": orchestration_run_id,
            "tools": _build_tools(self.db, ontology_id, dry_run),
        }
        if input_data:
            context.update(input_data)

        # execute python_code
        code = action.python_code or ""
        if not code.strip():
            result = {"status": "skipped", "message": "Action has no implementation code", "action_key": action.name_cn}
            _finish_run(self.db, run, result)
            return {**result, "run_id": run.id, "idempotency_key": idempotency_key, "orchestration_run_id": orchestration_run_id}

        import json as _json
        import math

        restricted_builtins = {
            "abs": abs, "all": all, "any": any, "bool": bool,
            "dict": dict, "float": float, "int": int, "len": len,
            "list": list, "max": max, "min": min, "range": range,
            "round": round, "set": set, "str": str, "sum": sum,
            "tuple": tuple, "zip": zip, "print": print,
            "__import__": __import__,
        }

        ns: dict[str, Any] = {"__builtins__": restricted_builtins, "math": math, "json": _json}
        try:
            exec(code, ns)
        except Exception as exc:
            result = {"status": "error", "message": f"Action compile error: {exc}", "action_key": action.name_cn}
            _finish_run(self.db, run, result, error=str(exc))
            return {**result, "run_id": run.id, "idempotency_key": idempotency_key, "orchestration_run_id": orchestration_run_id}

        execute_fn = ns.get("execute")
        if not callable(execute_fn):
            result = {"status": "error", "message": "No 'execute(context)' function found", "action_key": action.name_cn}
            _finish_run(self.db, run, result, error=result["message"])
            return {**result, "run_id": run.id, "idempotency_key": idempotency_key, "orchestration_run_id": orchestration_run_id}

        try:
            result = execute_fn(context)
            if isinstance(result, dict):
                result.setdefault("status", "unknown")
            else:
                result = {"status": "done", "message": str(result), "action_key": action.name_cn}
            _finish_run(self.db, run, result)
            return {**result, "run_id": run.id, "idempotency_key": idempotency_key, "orchestration_run_id": orchestration_run_id}
        except Exception as exc:
            result = {"status": "failed", "message": f"Action runtime error: {exc}", "action_key": action.name_cn}
            _finish_run(self.db, run, result, error=str(exc))
            return {**result, "run_id": run.id, "idempotency_key": idempotency_key, "orchestration_run_id": orchestration_run_id}


# ── action tools ───────────────────────────────────────────

def _build_tools(db: Session, ontology_id: str, dry_run: bool) -> dict[str, Any]:
    def execute_sql(data_source_id: str, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if dry_run:
            return {"dry_run": True, "rowcount": 0, "sql": sql, "params": params or {}}
        from app.models.v2.data_source import DataSource
        from sqlalchemy import create_engine, text as sa_text
        from urllib.parse import quote_plus

        source = db.query(DataSource).filter(
            DataSource.id == data_source_id,
            DataSource.ontology_id == ontology_id,
        ).first()
        if not source:
            raise RuntimeError(f"DataSource not found: {data_source_id}")
        cfg = source.db_config or {}
        db_type = cfg.get("db_type", "postgres")
        host = cfg.get("host", "localhost")
        port = str(cfg.get("port", 5432 if db_type == "postgres" else 3306))
        user = quote_plus(str(cfg.get("user", "")))
        pwd = quote_plus(str(cfg.get("password", "")))
        database = quote_plus(str(cfg.get("database", "")))
        if db_type == "postgres":
            url = f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{database}"
        elif db_type == "mysql":
            url = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{database}"
        else:
            raise RuntimeError(f"Unsupported db_type: {db_type}")
        engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})
        with engine.begin() as conn:
            result = conn.execute(sa_text(sql), params or {})
            return {"rowcount": result.rowcount}

    return {"execute_sql": execute_sql}


def _finish_run(db: Session, run, result: dict[str, Any], error: str | None = None) -> None:
    from datetime import datetime, timezone
    run.status = result.get("status", "unknown")
    run.result_payload = result
    run.error = error
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
