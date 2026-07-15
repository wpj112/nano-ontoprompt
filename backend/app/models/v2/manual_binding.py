"""Manual runtime bindings between ontology properties and external data columns."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ManualFieldBinding(Base):
    __tablename__ = "manual_field_bindings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ontology_id: Mapped[str] = mapped_column(
        String, ForeignKey("ontology_projects.id", ondelete="CASCADE"), nullable=False
    )
    object_type_id: Mapped[str] = mapped_column(String(200), nullable=False)
    property_name: Mapped[str] = mapped_column(String(200), nullable=False)
    data_source_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True
    )
    schema_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    table_name: Mapped[str] = mapped_column(String(200), nullable=False)
    column_name: Mapped[str] = mapped_column(String(200), nullable=False)
    primary_key_column: Mapped[str | None] = mapped_column(String(200), nullable=True)
    value_type: Mapped[str] = mapped_column(String(50), default="string")
    direction: Mapped[str] = mapped_column(String(20), default="read")
    transform_expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    read_only: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

class ManualLinkBinding(Base):
    __tablename__ = "manual_link_bindings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ontology_id: Mapped[str] = mapped_column(
        String, ForeignKey("ontology_projects.id", ondelete="CASCADE"), nullable=False
    )
    link_type_id: Mapped[str] = mapped_column(String(200), nullable=False)
    data_source_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True
    )
    schema_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    table_name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_object_type_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_key_column: Mapped[str] = mapped_column(String(200), nullable=False)
    target_object_type_id: Mapped[str] = mapped_column(String(200), nullable=False)
    target_key_column: Mapped[str] = mapped_column(String(200), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), default="out")
    relation_filters: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    property_bindings: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    transform_expression: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )



class ManualOrchestrationRun(Base):
    __tablename__ = "manual_orchestration_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ontology_id: Mapped[str] = mapped_column(
        String, ForeignKey("ontology_projects.id", ondelete="CASCADE"), nullable=False
    )
    external_run_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    agent_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="running")
    input_context: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    result_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ManualRuntimeActionRun(Base):
    __tablename__ = "manual_runtime_action_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ontology_id: Mapped[str] = mapped_column(
        String, ForeignKey("ontology_projects.id", ondelete="CASCADE"), nullable=False
    )
    action_key: Mapped[str] = mapped_column(String(200), nullable=False)
    orchestration_run_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="running")
    request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    result_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
