import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey

from app.db.base import Base


class ConfigTemplate(Base):
    """Platform-wide default template.

    Seeded by SmartSkale (via migration or platform admin API). Each template
    belongs to exactly one config_category and ships with a default subject,
    Markdown body, and a list of available ``{{placeholder}}`` variables.

    Tenants who have not customized a template implicitly inherit these values;
    tenant-specific overrides live in tenant_config_overrides.
    """

    __tablename__ = "config_templates"
    __table_args__ = (
        UniqueConstraint("code", name="uq_config_templates_code"),
        CheckConstraint(
            "template_type IN ('EMAIL', 'LETTER', 'NOTIFICATION', 'OTHER')",
            name="check_config_templates_type",
        ),
        CheckConstraint("sort_order >= 0", name="check_config_templates_sort_order"),
        CheckConstraint("version >= 1", name="check_config_templates_version"),
        Index("ix_config_templates_category_id", "category_id"),
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("config_categories.category_id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    template_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="EMAIL",
        server_default="EMAIL",
    )
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    placeholders: Mapped[list[dict]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="'[]'::jsonb",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="'{}'::jsonb",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
