import uuid

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db.base import Base


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "project_id"],
            ["projects.tenant_id", "projects.project_id"],
            name="fk_task_project",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "parent_task_id"],
            ["tasks.tenant_id", "tasks.task_id"],
            name="fk_parent_task",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assignee_id"],
            ["user_accounts.tenant_id", "user_accounts.id"],
            name="fk_task_assignee",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "technical_lead_id"],
            ["user_accounts.tenant_id", "user_accounts.id"],
            name="fk_task_tech_lead",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "functional_lead_id"],
            ["user_accounts.tenant_id", "user_accounts.id"],
            name="fk_task_func_lead",
        ),
        CheckConstraint(
            "status IN ('New', 'Assigned', 'In Progress', 'Blocked', 'On Hold', 'Under Review', 'Completed', 'Cancelled')",
            name="check_task_status",
        ),
        Index("idx_tasks_project_lookup", "tenant_id", "project_id"),
        Index("idx_tasks_assignee_lookup", "tenant_id", "assignee_id"),
        Index("idx_tasks_status_lookup", "tenant_id", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), primary_key=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    technical_lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    functional_lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    start_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[Date | None] = mapped_column(Date, nullable=True)
    estimated_hours: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    priority: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    blocked_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
