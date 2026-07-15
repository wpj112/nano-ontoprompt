"""Runtime Rule Service — evaluate ontology rules on objects."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


class RuntimeRuleService:
    """Evaluate ObjectRules against ontology instances."""

    def __init__(self, db: Session):
        self.db = db

    def evaluate(
        self,
        ontology_id: str,
        rule_key: str | None = None,
        *,
        subject_type_key: str | None = None,
        subject_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate rules against a subject.

        If *rule_key* is given, evaluate only that rule.
        Otherwise evaluate all applicable rules for the subject type.
        """
        from app.models.object_rule import ObjectRule
        from app.models.object_action import ObjectAction
        from app.models.v2.object_type import ObjectInstance, ObjectType

        # resolve subject
        instance = None
        object_type = None
        if subject_id and subject_type_key:
            object_type = self.db.query(ObjectType).filter(
                ObjectType.ontology_id == ontology_id,
                (ObjectType.name_en == subject_type_key)
                | (ObjectType.name_cn == subject_type_key)
                | (ObjectType.id == subject_type_key),
            ).first()
            if object_type:
                instance = self.db.query(ObjectInstance).filter(
                    ObjectInstance.ontology_id == ontology_id,
                    ObjectInstance.object_type_id == object_type.id,
                    (ObjectInstance.name_en == subject_id)
                    | (ObjectInstance.name_cn == subject_id)
                    | (ObjectInstance.id == subject_id),
                ).first()

        # find rules
        rules_query = self.db.query(ObjectRule).filter(
            ObjectRule.ontology_id == ontology_id,
        )
        if rule_key:
            rules_query = rules_query.filter(
                (ObjectRule.name_cn == rule_key)
                | (ObjectRule.id == rule_key)
            )
        elif object_type:
            rules_query = rules_query.filter(
                ObjectRule.object_type_id == object_type.id,
            )

        rules = rules_query.all()
        if not rules:
            return {"matched": False, "evaluations": [], "suggested_actions": []}

        # build context: static instance properties + resolved field bindings
        eval_context: dict[str, Any] = {
            "instance_id": instance.id if instance else None,
            "instance_name": instance.name_cn if instance else None,
            "type_name": object_type.name_cn if object_type else None,
            "type_name_en": object_type.name_en if object_type else None,
            "property_schema": object_type.property_schema if object_type else {},
        }
        if instance:
            eval_context.update(instance.properties or {})
        # resolve bound properties from external DB for materialized or virtual objects
        if object_type and subject_id:
            try:
                from app.services.v2.runtime.object_service import RuntimeObjectService
                obj_svc = RuntimeObjectService(self.db)
                object_key = instance.name_en or instance.name_cn or instance.id if instance else subject_id
                resolved = obj_svc.get_object(ontology_id, object_type, object_key)
                eval_context.update(resolved.get("properties", {}))
            except Exception:
                pass
        if context:
            eval_context.update(context)

        evaluations = []
        for rule in rules:
            result = _run_single_rule(rule, eval_context)
            evaluations.append({
                "rule_key": rule.name_cn,
                "rule_id": rule.id,
                "matched": result.get("passed", False),
                "severity": result.get("severity", "info"),
                "message": result.get("message", ""),
                "details": {k: v for k, v in result.items() if k not in ("passed", "message", "severity")},
            })

        # find suggested actions (linked via object_rule_id)
        action_ids = [r.id for r in rules if any(e["matched"] for e in evaluations)]
        suggested_actions = []
        if action_ids:
            actions = self.db.query(ObjectAction).filter(
                ObjectAction.ontology_id == ontology_id,
                ObjectAction.object_rule_id.in_(action_ids),
            ).all()
            suggested_actions = [
                {"action_key": a.name_cn, "action_id": a.id, "description": a.description}
                for a in actions
            ]

        matched = any(e["matched"] for e in evaluations)
        return {
            "matched": matched,
            "evaluations": evaluations,
            "suggested_actions": suggested_actions,
        }


def _run_single_rule(rule, context: dict) -> dict[str, Any]:
    """Execute python_code from an ObjectRule in a sandbox."""
    import json as _json
    import math

    code = rule.python_code or ""
    if not code.strip():
        return {"passed": False, "message": "Empty rule body"}

    restricted_builtins = {
        "abs": abs, "all": all, "any": any, "bool": bool,
        "dict": dict, "float": float, "int": int, "len": len,
        "list": list, "max": max, "min": min, "range": range,
        "round": round, "set": set, "str": str, "sum": sum,
        "tuple": tuple, "zip": zip, "print": print, "isinstance": isinstance,
        "__import__": __import__,
    }

    ns: dict[str, Any] = {"__builtins__": restricted_builtins, "math": math, "json": _json}
    try:
        exec(code, ns)
    except Exception as exc:
        return {"passed": False, "message": f"Rule compile error: {exc}"}

    check_fn = ns.get("check")
    if not callable(check_fn):
        return {"passed": False, "message": "No 'check(context)' function found in rule"}

    try:
        result = check_fn(context)
        if isinstance(result, dict):
            result.setdefault("passed", False)
            return result
        return {"passed": bool(result), "message": str(result)}
    except Exception as exc:
        return {"passed": False, "message": f"Rule runtime error: {exc}"}
