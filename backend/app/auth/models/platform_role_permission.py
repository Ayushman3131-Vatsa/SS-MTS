import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.common.models.base import Base


class PlatformRolePermission(Base):
    __tablename__ = "platform_role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_platform_role_permission"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    granted_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_admins.admin_id", ondelete="SET NULL"),
        nullable=True,
    )

    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
