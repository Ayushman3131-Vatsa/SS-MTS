import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user_account import UserAccount


class UserSession(Base):
    """Opaque browser session for platform admins and tenant users.

    Replaces the former ``browser_sessions`` table. Only the SHA-256 digest of
    the session / CSRF tokens is stored.
    """

    __tablename__ = "user_sessions"
    __table_args__ = (
        CheckConstraint(
            "principal_type IN ('platform_admin', 'tenant_user')",
            name="check_user_sessions_principal_type",
        ),
        CheckConstraint(
            "(principal_type = 'platform_admin' AND tenant_id IS NULL AND user_id IS NULL) OR "
            "(principal_type = 'tenant_user' AND tenant_id IS NOT NULL AND user_id IS NOT NULL)",
            name="check_user_sessions_tenant_context",
        ),
        UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
        Index("ix_user_sessions_principal", "principal_type", "principal_id"),
        Index("ix_user_sessions_expires_at", "expires_at"),
        Index("ix_user_sessions_tenant_user", "tenant_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    principal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    principal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_accounts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    device_label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[Optional["UserAccount"]] = relationship("UserAccount")

    @property
    def session_id(self) -> uuid.UUID:
        """Compatibility alias used by auth middleware / cleanup scripts."""
        return self.id
