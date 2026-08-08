import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKeyConstraint, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey

from app.db.base import Base


class TenantConfigOverride(Base):
    """Tenant-specific customization of a platform default template.

    Only rows that differ from the platform default exist here.  When a tenant
    has not customized a template, queries resolve to the default in
    config_templates.  Deleting an override row resets the tenant back to the
    platform default.

    The composite FK ``(tenant_id, updated_by_user_id)`` guarantees the
    editing user actually belongs to the same tenant — no cross-tenant
    data corruption is possible at the DB level.
    """

    __tablename__ = "tenant_config_overrides"
    __table_args__ = (
        UniqueConstraint("tenant_id", "template_id", name="uq_tenant_config_override"),
        ForeignKeyConstraint(
            ["tenant_id", "updated_by_user_id"],
            ["users.tenant_id", "users.user_id"],
            name="fk_override_updated_by",
            ondelete="RESTRICT",
        ),
        Index("ix_tenant_config_overrides_tenant_id", "tenant_id"),
    )

    override_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=False,
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("config_templates.template_id", ondelete="CASCADE"),
        nullable=False,
    )
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # An override row owns a complete content snapshot. This keeps later
    # platform edits from leaking into a tenant-customized template.
    body: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
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
