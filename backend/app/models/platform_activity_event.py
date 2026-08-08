import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import PlatformActivityType


class PlatformActivityEvent(Base):
    __tablename__ = "platform_activity_events"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_platform_activity_events_idempotency_key",
        ),
        CheckConstraint(
            "event_type IN ("
            "'TENANT_CREATED', 'PLAN_CHANGED', 'TENANT_SUSPENDED', "
            "'TENANT_REACTIVATED', 'DATABASE_ALLOCATION_READY', "
            "'DATABASE_ALLOCATION_FAILED', 'TENANT_ACTIVATED', "
            "'OFFERING_GRANTED', 'OFFERING_SUSPENDED', 'OFFERING_RESUMED', "
            "'OFFERING_DEACTIVATED', 'OFFERING_EXPIRED', "
            "'OFFERING_CATALOG_CREATED', 'OFFERING_CATALOG_UPDATED', "
            "'OFFERING_CATALOG_ACTIVATED', 'OFFERING_CATALOG_DEACTIVATED', "
            "'OFFERING_CATALOG_DELETED', 'DEFAULT_TEMPLATE_CREATED', "
            "'DEFAULT_TEMPLATE_UPDATED')",
            name="check_platform_activity_events_type",
        ),
        CheckConstraint(
            "actor_type IN ('PLATFORM_ADMIN', 'SYSTEM')",
            name="check_platform_activity_events_actor_type",
        ),
        CheckConstraint(
            "(actor_type = 'PLATFORM_ADMIN' AND actor_id IS NOT NULL) "
            "OR (actor_type = 'SYSTEM' AND actor_id IS NULL)",
            name="check_platform_activity_events_actor",
        ),
        Index(
            "ix_platform_activity_events_occurred_at",
            "occurred_at",
        ),
        Index(
            "ix_platform_activity_events_tenant_occurred_at",
            "tenant_id",
            "occurred_at",
        ),
    )

    activity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=PlatformActivityType.TENANT_CREATED.value,
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="SET NULL"),
        nullable=True,
    )
    tenant_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(30), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    event_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)

