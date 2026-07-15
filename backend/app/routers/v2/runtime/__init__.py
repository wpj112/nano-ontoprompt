"""Ontology Runtime API — agent-facing semantic interface.

This API layer is NOT for the frontend editor.  It is a stable contract for
third-party agent orchestration systems that operate on ontology semantics
rather than raw database tables and SQL.

Concepts exposed
----------------
- Ontology — the entire knowledge domain
- ObjectType — a class of objects (e.g. "Supplier", "Radar")
- Object — a specific instance identified by a business key
- Property — a named value on an object, resolved via field bindings
- Relation — a typed link between two objects (e.g. "DETECTS")
- Rule — a user-defined condition that can be evaluated against an object
- Action — a user-defined operation that can be executed

What agents NEVER see
---------------------
- Raw database table names or column names
- SQL statements
- DataSource connection strings
- Field binding internals (trim/upper/aggregate — all handled internally)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.ontology import OntologyProject
from app.models.object_action import ObjectAction
from app.models.object_rule import ObjectRule
from app.models.v2.object_type import LinkType, ObjectType

from app.services.v2.runtime import (
    RuntimeObjectService,
    RuntimeRelationService,
    RuntimeRuleService,
    RuntimeActionService,
)

router = APIRouter()


# ── guards ──────────────────────────────────────────────────

def _require_runtime(ontology_id: str, db: Session) -> OntologyProject:
    ont = db.query(OntologyProject).filter(OntologyProject.id == ontology_id).first()
    if not ont:
        raise HTTPException(404, "Ontology not found")
    if ont.build_mode != "manual":
        raise HTTPException(409, "Runtime API only supports build_mode=manual ontologies")
    return ont


def _resolve_type(ontology_id: str, type_key: str, db: Session) -> ObjectType:
    """Match ObjectType by id, name_en, or name_cn."""
    ot = db.query(ObjectType).filter(
        ObjectType.ontology_id == ontology_id,
        ObjectType.id == type_key,
    ).first()
    if not ot:
        ot = db.query(ObjectType).filter(
            ObjectType.ontology_id == ontology_id,
            (ObjectType.name_en == type_key) | (ObjectType.name_cn == type_key),
        ).first()
    if not ot:
        raise HTTPException(404, f"ObjectType not found: {type_key}")
    return ot


# ── 1. Metadata ─────────────────────────────────────────────

@router.get("/ontologies/{ontology_id}/metadata")
def get_metadata(ontology_id: str, db: Session = Depends(get_db)):
    """Discover the full ontology schema — types, properties, relations, rules, actions.

    This is the **first API call** any agent should make to understand
    what objects exist, what properties they have, what relationships
    connect them, and what rules/actions are available.
    """
    ont = _require_runtime(ontology_id, db)

    types = db.query(ObjectType).filter(ObjectType.ontology_id == ontology_id).all()
    link_types = db.query(LinkType).filter(LinkType.ontology_id == ontology_id).all()
    rules = db.query(ObjectRule).filter(ObjectRule.ontology_id == ontology_id).all()
    actions = db.query(ObjectAction).filter(ObjectAction.ontology_id == ontology_id).all()

    from app.models.v2.manual_binding import ManualFieldBinding, ManualLinkBinding
    bindings = db.query(ManualFieldBinding).filter(ManualFieldBinding.ontology_id == ontology_id).all()
    link_bindings = db.query(ManualLinkBinding).filter(ManualLinkBinding.ontology_id == ontology_id).all()

    return {
        "ontology": {
            "id": ont.id,
            "name": ont.name,
            "domain": ont.domain,
            "version": ont.version,
        },
        "object_types": [
            _serialize_type(t, bindings) for t in types
        ],
        "relations": [
            {
                "key": lt.name_en or lt.id,
                "label": lt.name_cn,
                "source_type_id": lt.source_object_type_id,
                "target_type_id": lt.target_object_type_id,
            }
            for lt in link_types
        ],
        "rules": [
            {"key": r.name_cn, "id": r.id, "description": r.description, "target_type_id": r.object_type_id}
            for r in rules
        ],
        "actions": [
            {"key": a.name_cn, "id": a.id, "description": a.description, "linked_rule_id": a.object_rule_id}
            for a in actions
        ],
        "runtime_capabilities": {
            "field_bindings": len(bindings),
            "link_bindings": len(link_bindings),
            "dynamic_relations": len(link_bindings) > 0,
        },
    }


def _serialize_type(t: ObjectType, bindings: list) -> dict:
    type_bindings = [b for b in bindings if b.object_type_id == t.id]
    return {
        "key": t.name_en or t.id,
        "label": t.name_cn,
        "id": t.id,
        "properties": [
            {
                "name": p,
                "type": (t.property_schema or {}).get(p, {}).get("type", "string") if isinstance(t.property_schema, dict) else "string",
                "unit": (t.property_schema or {}).get(p, {}).get("unit") if isinstance(t.property_schema, dict) else None,
                "bound": any(b.property_name == p for b in type_bindings),
            }
            for p in (list(t.property_schema.keys()) if isinstance(t.property_schema, dict) else [])
        ],
    }


# ── 2. Type Info ───────────────────────────────────────────

@router.get("/ontologies/{ontology_id}/types")
def list_types(ontology_id: str, db: Session = Depends(get_db)):
    """List all ObjectTypes in this ontology (lightweight, no property details)."""
    _require_runtime(ontology_id, db)
    from app.models.v2.manual_binding import ManualFieldBinding
    bindings = db.query(ManualFieldBinding).filter(ManualFieldBinding.ontology_id == ontology_id).all()
    types = db.query(ObjectType).filter(ObjectType.ontology_id == ontology_id).all()
    return {"types": [_serialize_type(t, bindings) for t in types]}


@router.get("/ontologies/{ontology_id}/types/{type_key}")
def get_type_info(ontology_id: str, type_key: str, db: Session = Depends(get_db)):
    """Detailed info about a single ObjectType."""
    _require_runtime(ontology_id, db)
    ot = _resolve_type(ontology_id, type_key, db)
    from app.models.v2.manual_binding import ManualFieldBinding
    bindings = db.query(ManualFieldBinding).filter(
        ManualFieldBinding.ontology_id == ontology_id,
        ManualFieldBinding.object_type_id == ot.id,
    ).all()
    return _serialize_type(ot, bindings)


# ── 3. Object Access ───────────────────────────────────────

@router.get("/ontologies/{ontology_id}/objects/{type_key}")
def list_objects(
    ontology_id: str,
    type_key: str,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List all known objects of a given type.

    Returns business keys that can be used in ``GET …/objects/{type}/{key}``.
    """
    _require_runtime(ontology_id, db)
    ot = _resolve_type(ontology_id, type_key, db)
    svc = RuntimeObjectService(db)
    keys = svc.list_object_keys(ontology_id, ot)
    items = []
    seen = set()
    for row in keys[: min(int(limit), len(keys))]:
        from app.models.v2.manual_binding import ManualFieldBinding
        bindings = db.query(ManualFieldBinding).filter(
            ManualFieldBinding.ontology_id == ontology_id,
            ManualFieldBinding.object_type_id == ot.id,
        ).all()
        pk_col = (bindings[0].primary_key_column or "code") if bindings else "id"
        pk_val = row.get(pk_col) or row.get(pk_col.lower())
        if pk_val is None:
            pk_val = next((v for v in row.values() if v is not None), None)
        if pk_val is None or str(pk_val) in seen:
            continue
        seen.add(str(pk_val))
        obj = svc.get_object(ontology_id, ot, str(pk_val))
        items.append(obj)
    return {"items": items, "count": len(items)}


@router.get("/ontologies/{ontology_id}/objects/{type_key}/{object_key}")
def get_object(ontology_id: str, type_key: str, object_key: str, db: Session = Depends(get_db)):
    """Read a single object with all bound properties resolved.

    Properties coming from external databases are resolved through
    field bindings → transform engine → type casting.
    The response includes ``_sources`` tracing each value back to
    its database origin.
    """
    _require_runtime(ontology_id, db)
    ot = _resolve_type(ontology_id, type_key, db)
    svc = RuntimeObjectService(db)
    obj = svc.get_object(ontology_id, ot, object_key)
    return {"object": obj}


class ObjectQueryRequest(BaseModel):
    filter: dict[str, Any] = Field(default_factory=dict, description="property filters; values can be literals or {op,value}")
    sort: list[dict[str, Any]] = Field(default_factory=list, description="optional sort specs: [{field,direction}]")
    limit: int = Field(default=20, ge=1, le=500)

@router.post("/ontologies/{ontology_id}/objects/{type_key}/query")
def query_objects(
    ontology_id: str,
    type_key: str,
    body: ObjectQueryRequest,
    db: Session = Depends(get_db),
):
    """Query objects with simple property filters.

    Example::

        POST .../objects/supplier/query
        {"filter": {"risk_level": "high"}, "limit": 20}

    Currently supports exact-match AND filters only.
    """
    _require_runtime(ontology_id, db)
    ot = _resolve_type(ontology_id, type_key, db)
    svc = RuntimeObjectService(db)
    items = svc.query_objects(
        ontology_id, ot,
        filter=body.filter,
        sort=body.sort,
        limit=body.limit,
    )
    return {"items": items, "count": len(items)}


# ── 4. Relations ───────────────────────────────────────────

@router.get("/ontologies/{ontology_id}/objects/{type_key}/{object_key}/relations")
def get_object_relations(
    ontology_id: str,
    type_key: str,
    object_key: str,
    relation: str | None = Query(None, description="filter by link type name"),
    db: Session = Depends(get_db),
):
    """Get all outgoing relationships for an object.

    Walk the ontology graph — what does this object connect to?
    """
    _require_runtime(ontology_id, db)
    ot = _resolve_type(ontology_id, type_key, db)

    from app.models.v2.object_type import ObjectInstance
    instance = db.query(ObjectInstance).filter(
        ObjectInstance.ontology_id == ontology_id,
        ObjectInstance.object_type_id == ot.id,
        (ObjectInstance.name_en == object_key) | (ObjectInstance.name_cn == object_key) | (ObjectInstance.id == object_key),
    ).first()

    svc = RuntimeRelationService(db)
    rels = svc.get_relations(
        ontology_id,
        ot,
        object_key,
        source_instance_id=instance.id if instance else None,
        relation_type=relation,
    )
    return {"relations": rels}


# ── 5. Rules ───────────────────────────────────────────────

class RuleEvaluateRequest(BaseModel):
    rule_key: str | None = Field(None, description="specific rule name, or omit to evaluate all")
    subject_type_key: str | None = Field(None, description="ObjectType for subject resolution")
    subject_id: str | None = Field(None, description="business key of the subject object")
    orchestration_run_id: str | None = Field(None, description="optional orchestration run scope for agent workflows")
    context: dict[str, Any] = Field(default_factory=dict, description="extra context for rule evaluation")

@router.post("/ontologies/{ontology_id}/rules/evaluate")
def evaluate_rules(ontology_id: str, body: RuleEvaluateRequest, db: Session = Depends(get_db)):
    """Evaluate rules (read-only, no side effects).

    Agents use this to check conditions before taking actions.
    """
    _require_runtime(ontology_id, db)
    svc = RuntimeRuleService(db)
    context = dict(body.context or {})
    if body.orchestration_run_id:
        context["orchestration_run_id"] = body.orchestration_run_id
    result = svc.evaluate(
        ontology_id,
        body.rule_key,
        subject_type_key=body.subject_type_key,
        subject_id=body.subject_id,
        context=context,
    )
    if body.orchestration_run_id:
        result["orchestration_run_id"] = body.orchestration_run_id
    return result


# ── 6. Actions ─────────────────────────────────────────────

class ActionExecuteRequest(BaseModel):
    subject_type_key: str | None = None
    subject_id: str | None = None
    input: dict[str, Any] = Field(default_factory=dict, description="input data for the action")
    dry_run: bool = Field(default=False, description="validate only, no side effects")
    idempotency_key: str | None = Field(None, description="deduplicate repeated agent action calls")
    orchestration_run_id: str | None = Field(None, description="optional orchestration run scope for agent workflows")

@router.post("/ontologies/{ontology_id}/actions/{action_key}/execute")
def execute_action(ontology_id: str, action_key: str, body: ActionExecuteRequest, db: Session = Depends(get_db)):
    """Execute an action on an object.

    Actions can have side effects. Use ``dry_run: true`` to validate first.
    """
    _require_runtime(ontology_id, db)
    svc = RuntimeActionService(db)
    result = svc.execute(
        ontology_id, action_key,
        subject_type_key=body.subject_type_key,
        subject_id=body.subject_id,
        input_data=body.input,
        dry_run=body.dry_run,
        idempotency_key=body.idempotency_key,
        orchestration_run_id=body.orchestration_run_id,
    )
    return result


@router.get("/ontologies/{ontology_id}/runs")
def list_action_runs(
    ontology_id: str,
    orchestration_run_id: str | None = Query(None, description="filter action runs by orchestration run"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    _require_runtime(ontology_id, db)
    from app.models.v2.manual_binding import ManualRuntimeActionRun
    query = db.query(ManualRuntimeActionRun).filter(ManualRuntimeActionRun.ontology_id == ontology_id)
    if orchestration_run_id:
        query = query.filter(ManualRuntimeActionRun.orchestration_run_id == orchestration_run_id)
    runs = query.order_by(ManualRuntimeActionRun.started_at.desc()).limit(limit).all()
    return {"runs": [_serialize_run(run) for run in runs]}


@router.get("/ontologies/{ontology_id}/runs/{run_id}")
def get_action_run(ontology_id: str, run_id: str, db: Session = Depends(get_db)):
    _require_runtime(ontology_id, db)
    from app.models.v2.manual_binding import ManualRuntimeActionRun
    run = db.query(ManualRuntimeActionRun).filter(
        ManualRuntimeActionRun.ontology_id == ontology_id,
        ManualRuntimeActionRun.id == run_id,
    ).first()
    if not run:
        raise HTTPException(404, "Run not found")
    return _serialize_run(run)


# ── 7. Orchestration Runs ──────────────────────────────────

class OrchestrationRunCreateRequest(BaseModel):
    external_run_id: str | None = Field(None, description="run id from the external orchestration system")
    agent_key: str | None = Field(None, description="agent/workflow identifier")
    input_context: dict[str, Any] = Field(default_factory=dict, description="initial orchestration context snapshot")


class OrchestrationRunCompleteRequest(BaseModel):
    status: str = Field(default="completed", description="completed, failed, cancelled, etc.")
    result_summary: dict[str, Any] = Field(default_factory=dict, description="final orchestration result summary")
    error: str | None = None


@router.post("/ontologies/{ontology_id}/orchestration-runs")
def create_orchestration_run(
    ontology_id: str,
    body: OrchestrationRunCreateRequest,
    db: Session = Depends(get_db),
):
    _require_runtime(ontology_id, db)
    from uuid import uuid4
    from app.models.v2.manual_binding import ManualOrchestrationRun

    run = ManualOrchestrationRun(
        id=str(uuid4()),
        ontology_id=ontology_id,
        external_run_id=body.external_run_id,
        agent_key=body.agent_key,
        status="running",
        input_context=body.input_context or {},
        result_summary={},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return _serialize_orchestration_run(run)


@router.get("/ontologies/{ontology_id}/orchestration-runs")
def list_orchestration_runs(
    ontology_id: str,
    agent_key: str | None = Query(None, description="optional agent/workflow filter"),
    status: str | None = Query(None, description="optional status filter"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    _require_runtime(ontology_id, db)
    from app.models.v2.manual_binding import ManualOrchestrationRun

    query = db.query(ManualOrchestrationRun).filter(ManualOrchestrationRun.ontology_id == ontology_id)
    if agent_key:
        query = query.filter(ManualOrchestrationRun.agent_key == agent_key)
    if status:
        query = query.filter(ManualOrchestrationRun.status == status)
    runs = query.order_by(ManualOrchestrationRun.started_at.desc()).limit(limit).all()
    return {"runs": [_serialize_orchestration_run(run) for run in runs]}


@router.get("/ontologies/{ontology_id}/orchestration-runs/{run_id}")
def get_orchestration_run(ontology_id: str, run_id: str, db: Session = Depends(get_db)):
    _require_runtime(ontology_id, db)
    from app.models.v2.manual_binding import ManualOrchestrationRun

    run = db.query(ManualOrchestrationRun).filter(
        ManualOrchestrationRun.ontology_id == ontology_id,
        ManualOrchestrationRun.id == run_id,
    ).first()
    if not run:
        raise HTTPException(404, "Orchestration run not found")
    return _serialize_orchestration_run(run)


@router.post("/ontologies/{ontology_id}/orchestration-runs/{run_id}/complete")
def complete_orchestration_run(
    ontology_id: str,
    run_id: str,
    body: OrchestrationRunCompleteRequest,
    db: Session = Depends(get_db),
):
    _require_runtime(ontology_id, db)
    from datetime import datetime, timezone
    from app.models.v2.manual_binding import ManualOrchestrationRun

    run = db.query(ManualOrchestrationRun).filter(
        ManualOrchestrationRun.ontology_id == ontology_id,
        ManualOrchestrationRun.id == run_id,
    ).first()
    if not run:
        raise HTTPException(404, "Orchestration run not found")

    run.status = body.status
    run.result_summary = body.result_summary or {}
    run.error = body.error
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return _serialize_orchestration_run(run)


def _serialize_run(run) -> dict:
    return {
        "id": run.id,
        "ontology_id": run.ontology_id,
        "action_key": run.action_key,
        "orchestration_run_id": run.orchestration_run_id,
        "idempotency_key": run.idempotency_key,
        "status": run.status,
        "request_payload": run.request_payload or {},
        "result_payload": run.result_payload or {},
        "error": run.error,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def _serialize_orchestration_run(run) -> dict:
    return {
        "id": run.id,
        "ontology_id": run.ontology_id,
        "external_run_id": run.external_run_id,
        "agent_key": run.agent_key,
        "status": run.status,
        "input_context": run.input_context or {},
        "result_summary": run.result_summary or {},
        "error": run.error,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
