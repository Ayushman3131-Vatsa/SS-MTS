import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint, Index, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyProgressLog(Base):
    __tablename__ = "daily_progress_logs"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "task_id"], ["tasks.tenant_id", "tasks.task_id"], name="fk_log_task"),
        ForeignKeyConstraint(
            ["tenant_id", "updated_by_user_id"], ["users.tenant_id", "users.user_id"], name="fk_log_author"
        ),
        Index("idx_daily_logs_task_lookup", "tenant_id", "task_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), primary_key=True
    )
    log_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    hours_worked: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    progress_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    log_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
