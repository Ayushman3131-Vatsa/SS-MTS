import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BrowserSession(Base):
    __tablename__ = "browser_sessions"
    __table_args__ = (
        CheckConstraint(
            "principal_type IN ('platform_admin', 'tenant_user')",
            name="check_browser_sessions_principal_type",
        ),
        CheckConstraint(
            "(principal_type = 'platform_admin' AND tenant_id IS NULL) OR "
            "(principal_type = 'tenant_user' AND tenant_id IS NOT NULL)",
            name="check_browser_sessions_tenant_context",
        ),
        UniqueConstraint("token_hash", name="uq_browser_sessions_token_hash"),
        Index("ix_browser_sessions_principal", "principal_type", "principal_id"),
        Index("ix_browser_sessions_expires_at", "expires_at"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    principal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    principal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
