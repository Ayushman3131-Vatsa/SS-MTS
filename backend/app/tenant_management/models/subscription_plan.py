import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db.base import Base
from app.tenant_management.models.enums import SubscriptionPlanStatus


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    __table_args__ = (
        UniqueConstraint("code", name="uq_subscription_plans_code"),
        CheckConstraint(
            "code IN ('FREE', 'BASIC', 'PRO', 'ENTERPRISE')",
            name="check_subscription_plans_code",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="check_subscription_plans_status",
        ),
        CheckConstraint(
            "price IS NULL OR price >= 0",
            name="check_subscription_plans_price",
        ),
        CheckConstraint(
            "max_users IS NULL OR max_users > 0",
            name="check_subscription_plans_max_users",
        ),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    billing_interval: Mapped[str | None] = mapped_column(String(20), nullable=True)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    features_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SubscriptionPlanStatus.ACTIVE.value,
        server_default=SubscriptionPlanStatus.ACTIVE.value,
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
