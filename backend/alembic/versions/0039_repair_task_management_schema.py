"""Repair Task Management schema when 0014/0015 changes were stamped but not applied.

Revision ID: 0039
Revises: 0038
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision: str = "0039"
down_revision: Union[str, None] = "0038"
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


def _table_exists(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def _column_exists(table: str, column: str) -> bool:
    return column in {item["name"] for item in inspect(op.get_bind()).get_columns(table)}


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    if not _column_exists(table, column.name):
        op.add_column(table, column)


def _create_rls_policy(table: str) -> None:
    op.execute(
        f"""
        DO $policy$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = '{table}'
                  AND policyname = '{table}_tenant_isolation'
            ) THEN
                CREATE POLICY {table}_tenant_isolation ON {table}
                USING (
                    current_setting('app.principal_type', true) = 'admin'
                    OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                )
                WITH CHECK (
                    current_setting('app.principal_type', true) = 'admin'
                    OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
                );
            END IF;
        END
        $policy$;
        """
    )


def _enable_rls_if_needed(table: str) -> None:
    if not _table_exists(table):
        return
    op.execute(
        f"""
        DO $rls$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname = '{table}'
                  AND c.relrowsecurity
            ) THEN
                ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
                ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
            END IF;
        END
        $rls$;
        """
    )


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    if _table_exists("projects"):
        _add_column_if_missing(
            "projects",
            sa.Column("project_key", sa.String(length=10), nullable=True),
        )
        _add_column_if_missing(
            "projects",
            sa.Column("next_task_number", sa.Integer(), server_default=sa.text("1"), nullable=False),
        )
        _add_column_if_missing(
            "projects",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        _add_column_if_missing(
            "projects",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        _add_column_if_missing(
            "projects",
            sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        )

    if _table_exists("tasks"):
        _add_column_if_missing("tasks", sa.Column("task_number", sa.Integer(), nullable=True))
        _add_column_if_missing(
            "tasks",
            sa.Column("task_type", sa.String(length=20), server_default=sa.text("'TASK'"), nullable=True),
        )
        _add_column_if_missing("tasks", sa.Column("reporter_id", postgresql.UUID(as_uuid=True), nullable=True))
        _add_column_if_missing(
            "tasks",
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        _add_column_if_missing(
            "tasks",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        _add_column_if_missing(
            "tasks",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        _add_column_if_missing("tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        _add_column_if_missing("tasks", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    if _table_exists("task_comments"):
        _add_column_if_missing(
            "task_comments",
            sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        )
        _add_column_if_missing(
            "task_comments",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        _add_column_if_missing(
            "task_comments",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )

    if _table_exists("daily_progress_logs"):
        _add_column_if_missing("daily_progress_logs", sa.Column("work_date", sa.Date(), nullable=True))
        _add_column_if_missing(
            "daily_progress_logs",
            sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        )
        _add_column_if_missing(
            "daily_progress_logs",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
        )
        _add_column_if_missing(
            "daily_progress_logs",
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        )

    op.execute(
        """
        UPDATE projects SET status = 'Not Started'
        WHERE status IS NULL OR status NOT IN
        ('Not Started', 'In Progress', 'On Hold', 'Completed', 'Cancelled')
        """
    )
    op.execute(
        """
        UPDATE projects SET priority = 'Medium'
        WHERE priority IS NULL OR priority NOT IN ('Low', 'Medium', 'High', 'Critical')
        """
    )
    op.execute(
        """
        UPDATE tasks SET status = 'New'
        WHERE status IS NULL OR status NOT IN
        ('New', 'Assigned', 'In Progress', 'Blocked', 'On Hold',
         'Under Review', 'Completed', 'Cancelled')
        """
    )
    op.execute(
        """
        UPDATE tasks SET priority = 'Medium'
        WHERE priority IS NULL OR priority NOT IN ('Low', 'Medium', 'High', 'Critical')
        """
    )
    op.execute("UPDATE tasks SET estimated_hours = 0 WHERE estimated_hours < 0")
    op.execute(
        """
        UPDATE projects p
        SET project_key = numbered.generated_key
        FROM (
            SELECT tenant_id, project_id,
                   'PRJ' || ROW_NUMBER() OVER (
                       PARTITION BY tenant_id ORDER BY project_id
                   )::text AS generated_key
            FROM projects
            WHERE project_key IS NULL
        ) numbered
        WHERE p.tenant_id = numbered.tenant_id
          AND p.project_id = numbered.project_id
        """
    )
    op.execute(
        """
        UPDATE tasks t
        SET task_number = numbered.generated_number
        FROM (
            SELECT tenant_id, task_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY tenant_id, project_id ORDER BY task_id
                   ) AS generated_number
            FROM tasks
            WHERE task_number IS NULL
        ) numbered
        WHERE t.tenant_id = numbered.tenant_id
          AND t.task_id = numbered.task_id
        """
    )
    op.execute(
        "UPDATE tasks SET task_type = CASE WHEN parent_task_id IS NULL THEN 'TASK' ELSE 'SUBTASK' END "
        "WHERE task_type IS NULL"
    )
    op.execute("UPDATE task_comments SET updated_at = created_at WHERE updated_at IS NULL")
    op.execute(
        "UPDATE daily_progress_logs SET work_date = log_date::date, updated_at = log_date "
        "WHERE work_date IS NULL"
    )
    op.execute(
        """
        UPDATE projects p
        SET next_task_number = COALESCE(numbers.maximum, 0) + 1
        FROM (
            SELECT tenant_id, project_id, MAX(task_number) AS maximum
            FROM tasks GROUP BY tenant_id, project_id
        ) numbers
        WHERE p.tenant_id = numbers.tenant_id
          AND p.project_id = numbers.project_id
        """
    )

    if not _table_exists("project_members"):
        op.create_table(
            "project_members",
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("added_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "role IN ('MANAGER', 'MEMBER', 'VIEWER')",
                name="check_project_member_role",
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["tenant_id", "project_id"],
                ["projects.tenant_id", "projects.project_id"],
                name="fk_project_member_project",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id", "user_id"],
                ["user_accounts.tenant_id", "user_accounts.id"],
                name="fk_project_member_user",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id", "added_by_user_id"],
                ["user_accounts.tenant_id", "user_accounts.id"],
                name="fk_project_member_added_by",
            ),
            sa.PrimaryKeyConstraint("tenant_id", "membership_id"),
            sa.UniqueConstraint(
                "tenant_id", "project_id", "user_id", name="uq_project_members_user"
            ),
        )
        op.create_index("idx_project_members_user", "project_members", ["tenant_id", "user_id"])
        op.create_index(
            "idx_project_members_project", "project_members", ["tenant_id", "project_id"]
        )

    if not _table_exists("task_links"):
        op.create_table(
            "task_links",
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("link_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("source_task_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("target_task_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("link_type", sa.String(length=20), nullable=False),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.CheckConstraint("source_task_id <> target_task_id", name="check_task_link_not_self"),
            sa.CheckConstraint(
                "link_type IN ('BLOCKS', 'RELATES_TO', 'DUPLICATES')",
                name="check_task_link_type",
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["tenant_id", "source_task_id"],
                ["tasks.tenant_id", "tasks.task_id"],
                name="fk_task_link_source",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id", "target_task_id"],
                ["tasks.tenant_id", "tasks.task_id"],
                name="fk_task_link_target",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id", "created_by_user_id"],
                ["user_accounts.tenant_id", "user_accounts.id"],
                name="fk_task_link_creator",
            ),
            sa.PrimaryKeyConstraint("tenant_id", "link_id"),
            sa.UniqueConstraint(
                "tenant_id",
                "source_task_id",
                "target_task_id",
                "link_type",
                name="uq_task_links_edge",
            ),
        )
        op.create_index("idx_task_links_source", "task_links", ["tenant_id", "source_task_id"])
        op.create_index("idx_task_links_target", "task_links", ["tenant_id", "target_task_id"])

    if not _table_exists("task_attachments"):
        op.create_table(
            "task_attachments",
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("attachment_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("storage_key", sa.String(length=255), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=False),
            sa.Column("media_type", sa.String(length=255), nullable=False),
            sa.Column("size_bytes", sa.BigInteger(), nullable=False),
            sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["tenant_id", "task_id"],
                ["tasks.tenant_id", "tasks.task_id"],
                name="fk_task_attachment_task",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id", "uploaded_by_user_id"],
                ["user_accounts.tenant_id", "user_accounts.id"],
                name="fk_task_attachment_uploader",
            ),
            sa.PrimaryKeyConstraint("tenant_id", "attachment_id"),
            sa.UniqueConstraint("storage_key", name="uq_task_attachments_storage_key"),
        )
        op.create_index(
            "idx_task_attachments_task",
            "task_attachments",
            ["tenant_id", "task_id", "deleted_at"],
        )

    if not _table_exists("task_activity_events"):
        op.create_table(
            "task_activity_events",
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("event_type", sa.String(length=50), nullable=False),
            sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column(
                "occurred_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["tenant_id", "task_id"],
                ["tasks.tenant_id", "tasks.task_id"],
                name="fk_task_activity_task",
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["tenant_id", "actor_user_id"],
                ["user_accounts.tenant_id", "user_accounts.id"],
                name="fk_task_activity_actor",
            ),
            sa.PrimaryKeyConstraint("tenant_id", "event_id"),
        )
        op.create_index(
            "idx_task_activity_task",
            "task_activity_events",
            ["tenant_id", "task_id", "occurred_at"],
        )

    if _table_exists("project_members"):
        op.execute(
            """
            INSERT INTO project_members
                (tenant_id, membership_id, project_id, user_id, role, added_by_user_id)
            SELECT tenant_id, uuid_generate_v4(), project_id, user_id,
                   CASE WHEN BOOL_OR(is_manager) THEN 'MANAGER' ELSE 'MEMBER' END,
                   NULL
            FROM (
                SELECT tenant_id, project_id, pm_id AS user_id, true AS is_manager
                FROM projects WHERE pm_id IS NOT NULL
                UNION ALL
                SELECT tenant_id, project_id, dm_id, true FROM projects WHERE dm_id IS NOT NULL
                UNION ALL
                SELECT tenant_id, project_id, assignee_id, false FROM tasks WHERE assignee_id IS NOT NULL
                UNION ALL
                SELECT tenant_id, project_id, technical_lead_id, false
                FROM tasks WHERE technical_lead_id IS NOT NULL
                UNION ALL
                SELECT tenant_id, project_id, functional_lead_id, false
                FROM tasks WHERE functional_lead_id IS NOT NULL
            ) candidates
            GROUP BY tenant_id, project_id, user_id
            ON CONFLICT (tenant_id, project_id, user_id) DO NOTHING
            """
        )

    if _table_exists("task_links"):
        op.execute(
            """
            INSERT INTO task_links
                (tenant_id, link_id, source_task_id, target_task_id, link_type, created_by_user_id)
            SELECT t.tenant_id, uuid_generate_v4(), t.blocked_by_id, t.task_id, 'BLOCKS',
                   COALESCE(t.created_by_user_id, t.reporter_id, t.assignee_id)
            FROM tasks t
            WHERE t.blocked_by_id IS NOT NULL
              AND COALESCE(t.created_by_user_id, t.reporter_id, t.assignee_id) IS NOT NULL
            ON CONFLICT DO NOTHING
            """
        )

    if _column_exists("projects", "project_key"):
        op.execute("ALTER TABLE projects ALTER COLUMN project_key SET NOT NULL")
    if _column_exists("tasks", "task_number"):
        op.execute("ALTER TABLE tasks ALTER COLUMN task_number SET NOT NULL")
    if _column_exists("tasks", "task_type"):
        op.execute("ALTER TABLE tasks ALTER COLUMN task_type SET NOT NULL")
    if _column_exists("daily_progress_logs", "work_date"):
        op.execute("ALTER TABLE daily_progress_logs ALTER COLUMN work_date SET NOT NULL")

    for table in RLS_TABLES:
        if _table_exists(table):
            _create_rls_policy(table)
            _enable_rls_if_needed(table)


def downgrade() -> None:
    # Repair migrations are intentionally not reversed.
    pass
