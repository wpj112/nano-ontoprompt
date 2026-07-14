"""Manual runtime bindings between ontology properties and external data columns."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
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
