import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey

from app.db.base import Base


class ConfigCategory(Base):
    """Groups configurable items by offering.

    Each offering can have multiple categories (e.g. Core HR → "Email Templates",
    "Letter Templates"). Categories are platform-wide definitions; tenants see
    only those whose offering_id matches their licensed offerings.
    """

    __tablename__ = "config_categories"
    __table_args__ = (
        UniqueConstraint("code", name="uq_config_categories_code"),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="check_config_categories_status",
        ),
        CheckConstraint("sort_order >= 0", name="check_config_categories_sort_order"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    offering_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("offerings.offering_id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    icon_key: Mapped[str] = mapped_column(String(50), nullable=False, default="file-text")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
        server_default="ACTIVE",
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
