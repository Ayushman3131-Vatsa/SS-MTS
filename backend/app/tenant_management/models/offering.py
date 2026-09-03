import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db.base import Base


class Offering(Base):
    __tablename__ = "offerings"
    __table_args__ = (
        UniqueConstraint("code", name="uq_offerings_code"),
        UniqueConstraint("route_slug", name="uq_offerings_route_slug"),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="check_offerings_status"),
        CheckConstraint(
            "role_type IN ('PLATFORM', 'TENANT', 'BOTH')",
            name="check_offerings_role_type",
        ),
        CheckConstraint("sort_order >= 0", name="check_offerings_sort_order"),
    )

    offering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    icon_key: Mapped[str] = mapped_column(String(50), nullable=False)
    route_slug: Mapped[str] = mapped_column(String(63), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
    )
    role_type: Mapped[str] = mapped_column(String(20), nullable=False, default="TENANT")
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
