import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "pm_id"],
            ["user_accounts.tenant_id", "user_accounts.id"],
            name="fk_project_pm",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "dm_id"],
            ["user_accounts.tenant_id", "user_accounts.id"],
            name="fk_project_dm",
        ),
        UniqueConstraint("tenant_id", "project_key", name="uq_projects_tenant_key"),
        CheckConstraint(
            "status IN ('Not Started', 'In Progress', 'Completed', 'On Hold', 'Cancelled')",
            name="check_project_status",
        ),
        CheckConstraint(
            "priority IN ('Low', 'Medium', 'High', 'Critical')",
            name="check_project_priority",
        ),
        CheckConstraint(
            "expected_end_date IS NULL OR start_date IS NULL OR expected_end_date >= start_date",
            name="check_project_date_order",
        ),
        CheckConstraint("next_task_number >= 1", name="check_project_next_task_number"),
        Index("idx_projects_status_lookup", "tenant_id", "status"),
        Index("idx_projects_active_lookup", "tenant_id", "archived_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_key: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Not Started")
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="Medium")
    pm_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    dm_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_task_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

