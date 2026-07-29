"""enforce baseline application invariants

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The original SQL used defaults without NOT NULL while the application
    # has always treated these fields as required. Backfill defensively before
    # making that invariant explicit in PostgreSQL and ORM metadata.
    op.execute("UPDATE audit_logs SET changed_at = CURRENT_TIMESTAMP WHERE changed_at IS NULL")
    op.execute(
        "UPDATE daily_progress_logs SET log_date = CURRENT_TIMESTAMP WHERE log_date IS NULL"
    )
    op.execute(
        "UPDATE platform_admins SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
    )
    op.execute("UPDATE projects SET version = 1 WHERE version IS NULL")
    op.execute(
        "UPDATE task_comments SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
    )
    op.execute("UPDATE tasks SET version = 1 WHERE version IS NULL")
    op.execute(
        "UPDATE tenants SET subscription_plan = 'Basic' WHERE subscription_plan IS NULL"
    )
    op.execute("UPDATE tenants SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    op.execute("UPDATE users SET status = 'Active' WHERE status IS NULL")
    op.execute("UPDATE users SET version = 1 WHERE version IS NULL")
    op.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

    op.alter_column(
        "audit_logs",
        "changed_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column(
        "daily_progress_logs",
        "log_date",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column(
        "platform_admins",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column("projects", "version", existing_type=sa.Integer(), nullable=False)
    op.alter_column(
        "task_comments",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column("tasks", "version", existing_type=sa.Integer(), nullable=False)
    op.alter_column(
        "tenants",
        "subscription_plan",
        existing_type=sa.String(length=50),
        nullable=False,
    )
    op.alter_column(
        "tenants",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.alter_column(
        "users",
        "status",
        existing_type=sa.String(length=20),
        nullable=False,
    )
    op.alter_column("users", "version", existing_type=sa.Integer(), nullable=False)
    op.alter_column(
        "users",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.alter_column("users", "version", existing_type=sa.Integer(), nullable=True)
    op.alter_column(
        "users",
        "status",
        existing_type=sa.String(length=20),
        nullable=True,
    )
    op.alter_column(
        "tenants",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.alter_column(
        "tenants",
        "subscription_plan",
        existing_type=sa.String(length=50),
        nullable=True,
    )
    op.alter_column("tasks", "version", existing_type=sa.Integer(), nullable=True)
    op.alter_column(
        "task_comments",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.alter_column("projects", "version", existing_type=sa.Integer(), nullable=True)
    op.alter_column(
        "platform_admins",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.alter_column(
        "daily_progress_logs",
        "log_date",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
    op.alter_column(
        "audit_logs",
        "changed_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )
