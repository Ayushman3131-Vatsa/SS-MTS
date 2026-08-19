"""Enforce Task Management contracts and row-level security.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RLS_TABLES = (
    "projects",
    "tasks",
    "task_comments",
    "daily_progress_logs",
    "project_members",
    "task_links",
    "task_attachments",
    "task_activity_events",
)


def upgrade() -> None:
    op.alter_column("projects", "project_key", existing_type=sa.String(length=10), nullable=False)
    op.alter_column("projects", "status", existing_type=sa.String(length=50), nullable=False)
    op.alter_column("projects", "priority", existing_type=sa.String(length=50), nullable=False)
    op.alter_column("tasks", "task_number", existing_type=sa.Integer(), nullable=False)
    op.alter_column("tasks", "task_type", existing_type=sa.String(length=20), nullable=False)
    op.alter_column("tasks", "status", existing_type=sa.String(length=50), nullable=False)
    op.alter_column("tasks", "priority", existing_type=sa.String(length=50), nullable=False)
    op.alter_column("daily_progress_logs", "work_date", existing_type=sa.Date(), nullable=False)

    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(RLS_TABLES):
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.alter_column("daily_progress_logs", "work_date", existing_type=sa.Date(), nullable=True)
    op.alter_column("tasks", "priority", existing_type=sa.String(length=50), nullable=True)
    op.alter_column("tasks", "status", existing_type=sa.String(length=50), nullable=True)
    op.alter_column("tasks", "task_type", existing_type=sa.String(length=20), nullable=True)
    op.alter_column("tasks", "task_number", existing_type=sa.Integer(), nullable=True)
    op.alter_column("projects", "priority", existing_type=sa.String(length=50), nullable=True)
    op.alter_column("projects", "status", existing_type=sa.String(length=50), nullable=True)
    op.alter_column("projects", "project_key", existing_type=sa.String(length=10), nullable=True)

