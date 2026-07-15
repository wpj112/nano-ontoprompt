"""Manual ontology authoring API boundary."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models.object_action import ObjectAction
from app.models.object_rule import ObjectRule
from app.models.ontology import OntologyProject
from app.models.v2.data_source import DataSource
from app.models.v2.manual_binding import ManualFieldBinding, ManualLinkBinding
from app.models.v2.object_type import Link, LinkType, ObjectInstance, ObjectType

router = APIRouter()


class LinkBindingCreate(BaseModel):
    link_type_id: str
    data_source_id: Optional[str] = None
    schema_name: Optional[str] = None
    table_name: str
    source_object_type_id: str
    source_key_column: str
    target_object_type_id: str
    target_key_column: str
    direction: str = "out"
    relation_filters: dict = {}
    property_bindings: dict = {}
    transform_expression: Optional[str] = None
    is_active: bool = True


class LinkBindingUpdate(BaseModel):
    link_type_id: Optional[str] = None
    data_source_id: Optional[str] = None
    schema_name: Optional[str] = None
    table_name: Optional[str] = None
    source_object_type_id: Optional[str] = None
    source_key_column: Optional[str] = None
    target_object_type_id: Optional[str] = None
    target_key_column: Optional[str] = None
    direction: Optional[str] = None
    relation_filters: Optional[dict] = None
    property_bindings: Optional[dict] = None
    transform_expression: Optional[str] = None
    is_active: Optional[bool] = None


class FieldBindingCreate(BaseModel):
    object_type_id: str
    property_name: str
    data_source_id: Optional[str] = None
    schema_name: Optional[str] = None
    table_name: str
    column_name: str
    primary_key_column: Optional[str] = None
    value_type: str = "string"
    direction: str = "read"
    transform_expression: Optional[str] = None
    is_required: bool = False
    read_only: bool = True


class FieldBindingUpdate(BaseModel):
    object_type_id: Optional[str] = None
    property_name: Optional[str] = None
    data_source_id: Optional[str] = None
    schema_name: Optional[str] = None
    table_name: Optional[str] = None
    column_name: Optional[str] = None
    primary_key_column: Optional[str] = None
    value_type: Optional[str] = None
    direction: Optional[str] = None
    transform_expression: Optional[str] = None
    is_required: Optional[bool] = None
    read_only: Optional[bool] = None


def _get_manual_ontology(ontology_id: str, db: Session) -> OntologyProject:
    ontology = db.query(OntologyProject).filter(OntologyProject.id == ontology_id).first()
    if not ontology:
        raise HTTPException(404, "Ontology not found")
    if ontology.build_mode != "manual":
        raise HTTPException(409, "Manual API only supports build_mode=manual ontologies")
    return ontology


def _serialize_link_binding(item: ManualLinkBinding) -> dict:
    return {
        "id": item.id,
        "ontology_id": item.ontology_id,
        "link_type_id": item.link_type_id,
        "data_source_id": item.data_source_id,
        "schema_name": item.schema_name,
        "table_name": item.table_name,
        "source_object_type_id": item.source_object_type_id,
        "source_key_column": item.source_key_column,
        "target_object_type_id": item.target_object_type_id,
        "target_key_column": item.target_key_column,
        "direction": item.direction,
        "relation_filters": item.relation_filters or {},
        "property_bindings": item.property_bindings or {},
        "transform_expression": item.transform_expression,
        "is_active": item.is_active,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _serialize_binding(item: ManualFieldBinding) -> dict:
    return {
        "id": item.id,
        "ontology_id": item.ontology_id,
        "object_type_id": item.object_type_id,
        "property_name": item.property_name,
        "data_source_id": item.data_source_id,
        "schema_name": item.schema_name,
        "table_name": item.table_name,
        "column_name": item.column_name,
        "primary_key_column": item.primary_key_column,
        "value_type": item.value_type,
        "direction": item.direction,
        "transform_expression": item.transform_expression,
        "is_required": item.is_required,
        "read_only": item.read_only,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _validate_link_binding_refs(ontology_id: str, body: LinkBindingCreate | LinkBindingUpdate, db: Session) -> None:
    link_type_id = getattr(body, "link_type_id", None)
    data_source_id = getattr(body, "data_source_id", None)
    source_object_type_id = getattr(body, "source_object_type_id", None)
    target_object_type_id = getattr(body, "target_object_type_id", None)
    if link_type_id:
        exists = db.query(LinkType).filter(LinkType.id == link_type_id, LinkType.ontology_id == ontology_id).first()
        if not exists:
            raise HTTPException(404, "LinkType not found")
    for object_type_id in [source_object_type_id, target_object_type_id]:
        if object_type_id:
            exists = db.query(ObjectType).filter(ObjectType.id == object_type_id, ObjectType.ontology_id == ontology_id).first()
            if not exists:
                raise HTTPException(404, "ObjectType not found")
    if data_source_id:
        exists = db.query(DataSource).filter(DataSource.id == data_source_id, DataSource.ontology_id == ontology_id).first()
        if not exists:
            raise HTTPException(404, "DataSource not found")


def _validate_binding_refs(ontology_id: str, body: FieldBindingCreate | FieldBindingUpdate, db: Session) -> None:
    object_type_id = getattr(body, "object_type_id", None)
    data_source_id = getattr(body, "data_source_id", None)
    if object_type_id:
        exists = db.query(ObjectType).filter(ObjectType.id == object_type_id, ObjectType.ontology_id == ontology_id).first()
        if not exists:
            raise HTTPException(404, "ObjectType not found")
    if data_source_id:
        exists = db.query(DataSource).filter(DataSource.id == data_source_id, DataSource.ontology_id == ontology_id).first()
        if not exists:
            raise HTTPException(404, "DataSource not found")


@router.get("/ontologies/{ontology_id}/summary")
def get_manual_summary(ontology_id: str, db: Session = Depends(get_db)):
    ontology = _get_manual_ontology(ontology_id, db)
    return {
        "data": {
            "id": ontology.id,
            "name": ontology.name,
            "domain": ontology.domain,
            "status": ontology.status,
            "build_mode": ontology.build_mode,
            "counts": {
                "object_types": db.query(func.count(ObjectType.id)).filter(ObjectType.ontology_id == ontology_id).scalar() or 0,
                "object_instances": db.query(func.count(ObjectInstance.id)).filter(ObjectInstance.ontology_id == ontology_id).scalar() or 0,
                "link_types": db.query(func.count(LinkType.id)).filter(LinkType.ontology_id == ontology_id).scalar() or 0,
                "links": db.query(func.count(Link.id)).filter(Link.ontology_id == ontology_id).scalar() or 0,
                "rules": db.query(func.count(ObjectRule.id)).filter(ObjectRule.ontology_id == ontology_id).scalar() or 0,
                "actions": db.query(func.count(ObjectAction.id)).filter(ObjectAction.ontology_id == ontology_id).scalar() or 0,
                "field_bindings": db.query(func.count(ManualFieldBinding.id)).filter(ManualFieldBinding.ontology_id == ontology_id).scalar() or 0,
                "link_bindings": db.query(func.count(ManualLinkBinding.id)).filter(ManualLinkBinding.ontology_id == ontology_id).scalar() or 0,
            },
        }
    }


@router.post("/ontologies/{ontology_id}/validate")
def validate_manual_ontology(ontology_id: str, db: Session = Depends(get_db)):
    _get_manual_ontology(ontology_id, db)
    warnings = []
    if db.query(ObjectType).filter(ObjectType.ontology_id == ontology_id).count() == 0:
        warnings.append({"code": "NO_OBJECT_TYPES", "message": "Manual ontology has no object types yet."})
    if db.query(ManualFieldBinding).filter(ManualFieldBinding.ontology_id == ontology_id).count() == 0:
        warnings.append({"code": "NO_FIELD_BINDINGS", "message": "No ontology properties are bound to data columns yet."})
    if db.query(ManualLinkBinding).filter(ManualLinkBinding.ontology_id == ontology_id).count() == 0:
        warnings.append({"code": "NO_LINK_BINDINGS", "message": "No ontology relationships are bound to data relation tables yet."})
    return {"data": {"valid": True, "warnings": warnings}}


@router.get("/ontologies/{ontology_id}/field-bindings")
def list_field_bindings(
    ontology_id: str,
    object_type_id: str = "",
    db: Session = Depends(get_db),
):
    _get_manual_ontology(ontology_id, db)
    q = db.query(ManualFieldBinding).filter(ManualFieldBinding.ontology_id == ontology_id)
    if object_type_id:
        q = q.filter(ManualFieldBinding.object_type_id == object_type_id)
    items = q.order_by(ManualFieldBinding.object_type_id, ManualFieldBinding.property_name).all()
    return {"data": [_serialize_binding(item) for item in items]}


@router.post("/ontologies/{ontology_id}/field-bindings", status_code=201)
def create_field_binding(ontology_id: str, body: FieldBindingCreate, db: Session = Depends(get_db)):
    _get_manual_ontology(ontology_id, db)
    _validate_binding_refs(ontology_id, body, db)
    existing = db.query(ManualFieldBinding).filter(
        ManualFieldBinding.ontology_id == ontology_id,
        ManualFieldBinding.object_type_id == body.object_type_id,
        ManualFieldBinding.property_name == body.property_name,
    ).first()
    if existing:
        raise HTTPException(409, "This ontology property already has a field binding")
    item = ManualFieldBinding(ontology_id=ontology_id, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"data": _serialize_binding(item)}


@router.put("/ontologies/{ontology_id}/field-bindings/{binding_id}")
def update_field_binding(ontology_id: str, binding_id: str, body: FieldBindingUpdate, db: Session = Depends(get_db)):
    _get_manual_ontology(ontology_id, db)
    item = db.query(ManualFieldBinding).filter(
        ManualFieldBinding.id == binding_id,
        ManualFieldBinding.ontology_id == ontology_id,
    ).first()
    if not item:
        raise HTTPException(404, "Field binding not found")
    _validate_binding_refs(ontology_id, body, db)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return {"data": _serialize_binding(item)}


@router.delete("/ontologies/{ontology_id}/field-bindings/{binding_id}", status_code=204)
def delete_field_binding(ontology_id: str, binding_id: str, db: Session = Depends(get_db)):
    _get_manual_ontology(ontology_id, db)
    item = db.query(ManualFieldBinding).filter(
        ManualFieldBinding.id == binding_id,
        ManualFieldBinding.ontology_id == ontology_id,
    ).first()
    if not item:
        raise HTTPException(404, "Field binding not found")
    db.delete(item)
    db.commit()

@router.get("/ontologies/{ontology_id}/link-bindings")
def list_link_bindings(
    ontology_id: str,
    link_type_id: str = "",
    db: Session = Depends(get_db),
):
    _get_manual_ontology(ontology_id, db)
    q = db.query(ManualLinkBinding).filter(ManualLinkBinding.ontology_id == ontology_id)
    if link_type_id:
        q = q.filter(ManualLinkBinding.link_type_id == link_type_id)
    items = q.order_by(ManualLinkBinding.link_type_id, ManualLinkBinding.table_name).all()
    return {"data": [_serialize_link_binding(item) for item in items]}


@router.post("/ontologies/{ontology_id}/link-bindings", status_code=201)
def create_link_binding(ontology_id: str, body: LinkBindingCreate, db: Session = Depends(get_db)):
    _get_manual_ontology(ontology_id, db)
    _validate_link_binding_refs(ontology_id, body, db)
    existing = db.query(ManualLinkBinding).filter(
        ManualLinkBinding.ontology_id == ontology_id,
        ManualLinkBinding.link_type_id == body.link_type_id,
        ManualLinkBinding.table_name == body.table_name,
        ManualLinkBinding.source_key_column == body.source_key_column,
        ManualLinkBinding.target_key_column == body.target_key_column,
    ).first()
    if existing:
        raise HTTPException(409, "This link binding already exists")
    item = ManualLinkBinding(ontology_id=ontology_id, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"data": _serialize_link_binding(item)}


@router.put("/ontologies/{ontology_id}/link-bindings/{binding_id}")
def update_link_binding(ontology_id: str, binding_id: str, body: LinkBindingUpdate, db: Session = Depends(get_db)):
    _get_manual_ontology(ontology_id, db)
    item = db.query(ManualLinkBinding).filter(
        ManualLinkBinding.id == binding_id,
        ManualLinkBinding.ontology_id == ontology_id,
    ).first()
    if not item:
        raise HTTPException(404, "Link binding not found")
    _validate_link_binding_refs(ontology_id, body, db)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return {"data": _serialize_link_binding(item)}


@router.delete("/ontologies/{ontology_id}/link-bindings/{binding_id}", status_code=204)
def delete_link_binding(ontology_id: str, binding_id: str, db: Session = Depends(get_db)):
    _get_manual_ontology(ontology_id, db)
    item = db.query(ManualLinkBinding).filter(
        ManualLinkBinding.id == binding_id,
        ManualLinkBinding.ontology_id == ontology_id,
    ).first()
    if not item:
        raise HTTPException(404, "Link binding not found")
    db.delete(item)
    db.commit()

