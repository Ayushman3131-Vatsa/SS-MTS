import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DatabaseIsolationMode


class TenantDatabaseAllocation(Base):
    __tablename__ = "tenant_database_allocations"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('SHARED', 'DEDICATED')",
            name="check_tenant_database_allocations_mode",
        ),
        CheckConstraint(
            "provisioning_state IN ('PENDING', 'READY', 'FAILED')",
            name="check_tenant_database_allocations_state",
        ),
        CheckConstraint(
            "(provisioning_state = 'READY' AND ready_at IS NOT NULL) "
            "OR (provisioning_state <> 'READY' AND ready_at IS NULL)",
            name="check_tenant_database_allocations_ready_at",
        ),
        Index(
            "ix_tenant_database_allocations_dashboard",
            "mode",
            "provisioning_state",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    )
    mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DatabaseIsolationMode.SHARED.value,
        server_default=DatabaseIsolationMode.SHARED.value,
    )
    provisioning_state: Mapped[str] = mapped_column(
        String(20),
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
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
