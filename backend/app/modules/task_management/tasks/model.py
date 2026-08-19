import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


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
            ["tenant_id", "blocked_by_id"],
            ["tasks.tenant_id", "tasks.task_id"],
            name="fk_task_blocked_by",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assignee_id"],
            ["users.tenant_id", "users.user_id"],
            name="fk_task_assignee",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "technical_lead_id"],
            ["users.tenant_id", "users.user_id"],
            name="fk_task_tech_lead",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "functional_lead_id"],
            ["users.tenant_id", "users.user_id"],
            name="fk_task_func_lead",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "reporter_id"],
            ["users.tenant_id", "users.user_id"],
            name="fk_task_reporter",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.user_id"],
            name="fk_task_created_by",
        ),
        UniqueConstraint(
            "tenant_id", "project_id", "task_number", name="uq_tasks_project_number"
        ),
        CheckConstraint(
            "status IN ('New', 'Assigned', 'In Progress', 'Blocked', 'On Hold', "
            "'Under Review', 'Completed', 'Cancelled')",
            name="check_task_status",
        ),
        CheckConstraint(
            "priority IN ('Low', 'Medium', 'High', 'Critical')",
            name="check_task_priority",
        ),
        CheckConstraint(
            "task_type IN ('EPIC', 'STORY', 'TASK', 'BUG', 'SUBTASK')",
            name="check_task_type",
        ),
        CheckConstraint("estimated_hours >= 0", name="check_task_estimated_hours"),
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="check_task_date_order",
        ),
        CheckConstraint("task_number >= 1", name="check_task_number"),
        CheckConstraint("blocked_by_id IS NULL OR blocked_by_id <> task_id", name="check_task_not_self_blocked"),
        Index("idx_tasks_project_lookup", "tenant_id", "project_id"),
        Index("idx_tasks_assignee_lookup", "tenant_id", "assignee_id"),
        Index("idx_tasks_status_lookup", "tenant_id", "status"),
        Index("idx_tasks_project_status", "tenant_id", "project_id", "status"),
        Index("idx_tasks_due_lookup", "tenant_id", "end_date"),
        Index("idx_tasks_active_lookup", "tenant_id", "archived_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    task_number: Mapped[int] = mapped_column(Integer, nullable=False)
    task_type: Mapped[str] = mapped_column(String(20), nullable=False, default="TASK")
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    technical_lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    functional_lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reporter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="Medium")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="New")
    blocked_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskLink(Base):
    __tablename__ = "task_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "source_task_id"],
            ["tasks.tenant_id", "tasks.task_id"],
            name="fk_task_link_source",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "target_task_id"],
            ["tasks.tenant_id", "tasks.task_id"],
            name="fk_task_link_target",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"],
            ["users.tenant_id", "users.user_id"],
            name="fk_task_link_creator",
        ),
        UniqueConstraint(
            "tenant_id",
            "source_task_id",
            "target_task_id",
            "link_type",
            name="uq_task_links_edge",
        ),
        CheckConstraint("source_task_id <> target_task_id", name="check_task_link_not_self"),
        CheckConstraint(
            "link_type IN ('BLOCKS', 'RELATES_TO', 'DUPLICATES')",
            name="check_task_link_type",
        ),
        Index("idx_task_links_source", "tenant_id", "source_task_id"),
        Index("idx_task_links_target", "tenant_id", "target_task_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
        primary_key=True,
    )
    link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    link_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
