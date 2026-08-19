import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import TenantStatus


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        UniqueConstraint("workspace_slug", name="uq_tenants_workspace_slug"),
        UniqueConstraint("tenant_code", name="uq_tenants_tenant_code"),
        CheckConstraint(
            "workspace_slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
            name="check_tenants_workspace_slug",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'SUSPENDED')",
            name="check_tenants_status",
        ),
        CheckConstraint(
            "tenant_code ~ '^[A-Z0-9][A-Z0-9_-]*$'",
            name="check_tenants_tenant_code",
        ),
        Index("ix_tenants_created_at", "created_at"),
        Index("ix_tenants_status_created_at", "status", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_code: Mapped[str] = mapped_column(String(30), nullable=False)
    workspace_slug: Mapped[str] = mapped_column(String(63), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_identifier: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state_province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(CITEXT(), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    alternate_contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    alternate_contact_email: Mapped[str | None] = mapped_column(CITEXT(), nullable=True)
    alternate_contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    subscription_plan: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Free",
        server_default="Free",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TenantStatus.ACTIVE.value,
        server_default=TenantStatus.ACTIVE.value,
    )
    created_by_admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("platform_admins.admin_id"), nullable=False
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
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
