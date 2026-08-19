"""Expand the Task Management offering without enabling RLS.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import make_url

from app.core.config import get_settings


revision: str = "0014"
down_revision: Union[str, None] = "0013"
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


def _create_rls_policy(table: str) -> None:
    op.execute(
        f"""
        CREATE POLICY {table}_tenant_isolation ON {table}
        USING (
            current_setting('app.principal_type', true) = 'admin'
            OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        WITH CHECK (
            current_setting('app.principal_type', true) = 'admin'
            OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        """
    )


def _grant_runtime_role() -> None:
    settings = get_settings()
    runtime_role = make_url(settings.database_url).username
    if not runtime_role:
        return
    if not settings.is_development:
        role_literal = "'" + runtime_role.replace("'", "''") + "'"
        table_literals = ", ".join(f"'{table}'" for table in RLS_TABLES)
        op.execute(
            f"""
            DO $task_management_role_check$
            DECLARE privileged boolean;
            BEGIN
                SELECT rolsuper OR rolbypassrls INTO privileged
                FROM pg_roles WHERE rolname = {role_literal};
                IF privileged IS NULL THEN
                    RAISE EXCEPTION 'Runtime database role does not exist';
                ELSIF privileged THEN
                    RAISE EXCEPTION 'Runtime database role must not be superuser or BYPASSRLS';
                END IF;
                IF EXISTS (
                    SELECT 1
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public'
                      AND c.relname IN ({table_literals})
                      AND pg_get_userbyid(c.relowner) = {role_literal}
                ) THEN
                    RAISE EXCEPTION 'Runtime database role must not own Task Management tables';
                END IF;
            END
            $task_management_role_check$
            """
        )
    quoted_role = op.get_bind().dialect.identifier_preparer.quote(runtime_role)
    op.execute(f"GRANT USAGE ON SCHEMA public TO {quoted_role}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {quoted_role}"
    )
    op.execute(
        f"REVOKE UPDATE, DELETE ON TABLE task_activity_events FROM {quoted_role}"
    )
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted_role}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {quoted_role}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {quoted_role}"
    )


def upgrade() -> None:
    # Expand existing aggregates. New required fields stay nullable until
    # deterministic backfills have completed and the contract migration runs.
    op.add_column("projects", sa.Column("project_key", sa.String(length=10), nullable=True))
    op.add_column(
        "projects",
        sa.Column("next_task_number", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column(
        "projects",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.add_column(
        "projects",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.add_column("projects", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("tasks", sa.Column("task_number", sa.Integer(), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("task_type", sa.String(length=20), server_default=sa.text("'TASK'"), nullable=True),
    )
    op.add_column("tasks", sa.Column("reporter_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("tasks", sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "tasks",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.add_column(
        "tasks",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.add_column("tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column(
        "task_comments", sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False)
    )
    op.add_column(
        "task_comments",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.add_column("task_comments", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("daily_progress_logs", sa.Column("work_date", sa.Date(), nullable=True))
    op.add_column(
        "daily_progress_logs", sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False)
    )
    op.add_column(
        "daily_progress_logs",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.add_column("daily_progress_logs", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    # Normalize legacy nullable/free-form values before adding constraints.
    op.execute(
        "UPDATE projects SET status = 'Not Started' "
        "WHERE status IS NULL OR status NOT IN "
        "('Not Started', 'In Progress', 'On Hold', 'Completed', 'Cancelled')"
    )
    op.execute(
        "UPDATE projects SET priority = 'Medium' "
        "WHERE priority IS NULL OR priority NOT IN ('Low', 'Medium', 'High', 'Critical')"
    )
    op.execute(
        "UPDATE projects SET expected_end_date = start_date "
        "WHERE start_date IS NOT NULL AND expected_end_date < start_date"
    )
    op.execute(
        "UPDATE tasks SET status = 'New' "
        "WHERE status IS NULL OR status NOT IN "
        "('New', 'Assigned', 'In Progress', 'Blocked', 'On Hold', "
        "'Under Review', 'Completed', 'Cancelled')"
    )
    op.execute(
        "UPDATE tasks SET priority = 'Medium' "
        "WHERE priority IS NULL OR priority NOT IN ('Low', 'Medium', 'High', 'Critical')"
    )
    op.execute("UPDATE tasks SET estimated_hours = 0 WHERE estimated_hours < 0")
    op.execute(
        "UPDATE tasks SET end_date = start_date "
        "WHERE start_date IS NOT NULL AND end_date < start_date"
    )
    op.execute(
        "UPDATE tasks child SET blocked_by_id = NULL WHERE blocked_by_id IS NOT NULL AND NOT EXISTS ("
        "SELECT 1 FROM tasks blocker WHERE blocker.tenant_id = child.tenant_id "
        "AND blocker.task_id = child.blocked_by_id AND blocker.project_id = child.project_id)"
    )
    op.execute("UPDATE tasks SET blocked_by_id = NULL WHERE blocked_by_id = task_id")
    op.execute(
        "UPDATE daily_progress_logs SET hours_worked = 0.01 WHERE hours_worked <= 0"
    )
    op.execute(
        "UPDATE daily_progress_logs SET hours_worked = 24 WHERE hours_worked > 24"
    )

    op.execute(
        """
        WITH numbered AS (
            SELECT tenant_id, project_id,
                   'PRJ' || ROW_NUMBER() OVER (
                       PARTITION BY tenant_id ORDER BY project_id
                   )::text AS generated_key
            FROM projects
        )
        UPDATE projects p SET project_key = numbered.generated_key
        FROM numbered
        WHERE p.tenant_id = numbered.tenant_id AND p.project_id = numbered.project_id
        """
    )
    op.execute(
        """
        WITH numbered AS (
            SELECT tenant_id, task_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY tenant_id, project_id ORDER BY task_id
                   ) AS generated_number
            FROM tasks
        )
        UPDATE tasks t SET task_number = numbered.generated_number
        FROM numbered
        WHERE t.tenant_id = numbered.tenant_id AND t.task_id = numbered.task_id
        """
    )
    op.execute("UPDATE tasks SET task_type = CASE WHEN parent_task_id IS NULL THEN 'TASK' ELSE 'SUBTASK' END")
    op.execute(
        """
        WITH create_audit AS (
            SELECT DISTINCT ON (tenant_id, entity_id)
                   tenant_id, entity_id, changed_at
            FROM audit_logs
            WHERE entity_type = 'project' AND action = 'CREATE'
            ORDER BY tenant_id, entity_id, changed_at
        )
        UPDATE projects p
        SET created_at = a.changed_at, updated_at = a.changed_at
        FROM create_audit a
        WHERE p.tenant_id = a.tenant_id AND p.project_id = a.entity_id
        """
    )
    op.execute(
        """
        WITH create_audit AS (
            SELECT DISTINCT ON (tenant_id, entity_id)
                   tenant_id, entity_id, changed_at, changed_by_user_id
            FROM audit_logs
            WHERE entity_type = 'task' AND action = 'CREATE'
            ORDER BY tenant_id, entity_id, changed_at
        )
        UPDATE tasks t
        SET created_at = a.changed_at,
            updated_at = a.changed_at,
            created_by_user_id = a.changed_by_user_id,
            reporter_id = a.changed_by_user_id
        FROM create_audit a
        WHERE t.tenant_id = a.tenant_id AND t.task_id = a.entity_id
        """
    )
    op.execute(
        "UPDATE tasks SET completed_at = updated_at "
        "WHERE status = 'Completed' AND completed_at IS NULL"
    )
    op.execute("UPDATE task_comments SET updated_at = created_at")
    op.execute(
        "UPDATE daily_progress_logs SET work_date = log_date::date, updated_at = log_date"
    )
    op.execute(
        """
        UPDATE projects p SET next_task_number = COALESCE(numbers.maximum, 0) + 1
        FROM (
            SELECT tenant_id, project_id, MAX(task_number) AS maximum
            FROM tasks GROUP BY tenant_id, project_id
        ) numbers
        WHERE p.tenant_id = numbers.tenant_id AND p.project_id = numbers.project_id
        """
    )

    op.create_unique_constraint("uq_projects_tenant_key", "projects", ["tenant_id", "project_key"])
    # check_project_status is owned by the initial schema migration. Its
    # allowed values already match the canonical workflow, so recreating it
    # here would fail every database upgraded through the normal revision
    # chain with DuplicateObjectError.
    op.create_check_constraint(
        "check_project_priority", "projects", "priority IN ('Low', 'Medium', 'High', 'Critical')"
    )
    op.create_check_constraint(
        "check_project_date_order",
        "projects",
        "expected_end_date IS NULL OR start_date IS NULL OR expected_end_date >= start_date",
    )
    op.create_check_constraint("check_project_next_task_number", "projects", "next_task_number >= 1")
    op.create_index("idx_projects_status_lookup", "projects", ["tenant_id", "status"])
    op.create_index("idx_projects_active_lookup", "projects", ["tenant_id", "archived_at"])

    op.create_unique_constraint(
        "uq_tasks_project_number", "tasks", ["tenant_id", "project_id", "task_number"]
    )
    # check_task_status is likewise retained from migration 0001.
    op.create_check_constraint(
        "check_task_priority", "tasks", "priority IN ('Low', 'Medium', 'High', 'Critical')"
    )
    op.create_check_constraint(
        "check_task_type", "tasks", "task_type IN ('EPIC', 'STORY', 'TASK', 'BUG', 'SUBTASK')"
    )
    op.create_check_constraint("check_task_estimated_hours", "tasks", "estimated_hours >= 0")
    op.create_check_constraint(
        "check_task_date_order", "tasks", "end_date IS NULL OR start_date IS NULL OR end_date >= start_date"
    )
    op.create_check_constraint("check_task_number", "tasks", "task_number >= 1")
    op.create_check_constraint("check_task_not_self_blocked", "tasks", "blocked_by_id IS NULL OR blocked_by_id <> task_id")
    op.create_foreign_key(
        "fk_task_blocked_by", "tasks", "tasks", ["tenant_id", "blocked_by_id"], ["tenant_id", "task_id"]
    )
    op.create_foreign_key(
        "fk_task_reporter", "tasks", "user_accounts", ["tenant_id", "reporter_id"], ["tenant_id", "id"]
    )
    op.create_foreign_key(
        "fk_task_created_by", "tasks", "user_accounts", ["tenant_id", "created_by_user_id"], ["tenant_id", "id"]
    )
    op.create_index("idx_tasks_project_status", "tasks", ["tenant_id", "project_id", "status"])
    op.create_index("idx_tasks_due_lookup", "tasks", ["tenant_id", "end_date"])
    op.create_index("idx_tasks_active_lookup", "tasks", ["tenant_id", "archived_at"])
    op.create_check_constraint(
        "check_daily_log_hours", "daily_progress_logs", "hours_worked > 0 AND hours_worked <= 24"
    )

    op.create_table(
        "project_members",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("added_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("role IN ('MANAGER', 'MEMBER', 'VIEWER')", name="check_project_member_role"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "project_id"], ["projects.tenant_id", "projects.project_id"],
            name="fk_project_member_project", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "user_id"], ["user_accounts.tenant_id", "user_accounts.id"], name="fk_project_member_user"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "added_by_user_id"], ["user_accounts.tenant_id", "user_accounts.id"], name="fk_project_member_added_by"
        ),
        sa.PrimaryKeyConstraint("tenant_id", "membership_id"),
        sa.UniqueConstraint("tenant_id", "project_id", "user_id", name="uq_project_members_user"),
    )
    op.create_index("idx_project_members_user", "project_members", ["tenant_id", "user_id"])
    op.create_index("idx_project_members_project", "project_members", ["tenant_id", "project_id"])

    op.execute(
        """
        INSERT INTO project_members
            (tenant_id, membership_id, project_id, user_id, role, added_by_user_id)
        SELECT tenant_id, uuid_generate_v4(), project_id, user_id,
               CASE WHEN BOOL_OR(is_manager) THEN 'MANAGER' ELSE 'MEMBER' END,
               NULL
        FROM (
            SELECT tenant_id, project_id, pm_id AS user_id, true AS is_manager FROM projects WHERE pm_id IS NOT NULL
            UNION ALL
            SELECT tenant_id, project_id, dm_id, true FROM projects WHERE dm_id IS NOT NULL
            UNION ALL
            SELECT tenant_id, project_id, assignee_id, false FROM tasks WHERE assignee_id IS NOT NULL
            UNION ALL
            SELECT tenant_id, project_id, technical_lead_id, false FROM tasks WHERE technical_lead_id IS NOT NULL
            UNION ALL
            SELECT tenant_id, project_id, functional_lead_id, false FROM tasks WHERE functional_lead_id IS NOT NULL
        ) candidates
        GROUP BY tenant_id, project_id, user_id
        ON CONFLICT (tenant_id, project_id, user_id) DO NOTHING
        """
    )

    op.create_table(
        "task_links",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("link_type", sa.String(length=20), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("source_task_id <> target_task_id", name="check_task_link_not_self"),
        sa.CheckConstraint("link_type IN ('BLOCKS', 'RELATES_TO', 'DUPLICATES')", name="check_task_link_type"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "source_task_id"], ["tasks.tenant_id", "tasks.task_id"],
            name="fk_task_link_source", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "target_task_id"], ["tasks.tenant_id", "tasks.task_id"],
            name="fk_task_link_target", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by_user_id"], ["user_accounts.tenant_id", "user_accounts.id"],
            name="fk_task_link_creator"
        ),
        sa.PrimaryKeyConstraint("tenant_id", "link_id"),
        sa.UniqueConstraint(
            "tenant_id", "source_task_id", "target_task_id", "link_type", name="uq_task_links_edge"
        ),
    )
    op.create_index("idx_task_links_source", "task_links", ["tenant_id", "source_task_id"])
    op.create_index("idx_task_links_target", "task_links", ["tenant_id", "target_task_id"])
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
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"], ["tasks.tenant_id", "tasks.task_id"],
            name="fk_task_attachment_task", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "uploaded_by_user_id"], ["user_accounts.tenant_id", "user_accounts.id"],
            name="fk_task_attachment_uploader"
        ),
        sa.PrimaryKeyConstraint("tenant_id", "attachment_id"),
        sa.UniqueConstraint("storage_key", name="uq_task_attachments_storage_key"),
    )
    op.create_index(
        "idx_task_attachments_task", "task_attachments", ["tenant_id", "task_id", "deleted_at"]
    )

    op.create_table(
        "task_activity_events",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"], ["tasks.tenant_id", "tasks.task_id"],
            name="fk_task_activity_task", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "actor_user_id"], ["user_accounts.tenant_id", "user_accounts.id"],
            name="fk_task_activity_actor"
        ),
        sa.PrimaryKeyConstraint("tenant_id", "event_id"),
    )
    op.create_index(
        "idx_task_activity_task", "task_activity_events", ["tenant_id", "task_id", "occurred_at"]
    )

    # Policies are created now but intentionally remain disabled until every
    # running application instance sets transaction-local request context.
    for table in RLS_TABLES:
        _create_rls_policy(table)
    _grant_runtime_role()


def downgrade() -> None:
    for table in reversed(RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")

    op.drop_index("idx_task_activity_task", table_name="task_activity_events")
    op.drop_table("task_activity_events")
    op.drop_index("idx_task_attachments_task", table_name="task_attachments")
    op.drop_table("task_attachments")
    op.drop_index("idx_task_links_target", table_name="task_links")
    op.drop_index("idx_task_links_source", table_name="task_links")
    op.drop_table("task_links")
    op.drop_index("idx_project_members_project", table_name="project_members")
    op.drop_index("idx_project_members_user", table_name="project_members")
    op.drop_table("project_members")

    op.drop_constraint("check_daily_log_hours", "daily_progress_logs", type_="check")
    op.drop_index("idx_tasks_active_lookup", table_name="tasks")
    op.drop_index("idx_tasks_due_lookup", table_name="tasks")
    op.drop_index("idx_tasks_project_status", table_name="tasks")
    op.drop_constraint("fk_task_created_by", "tasks", type_="foreignkey")
    op.drop_constraint("fk_task_reporter", "tasks", type_="foreignkey")
    op.drop_constraint("fk_task_blocked_by", "tasks", type_="foreignkey")
    op.drop_constraint("check_task_not_self_blocked", "tasks", type_="check")
    op.drop_constraint("check_task_number", "tasks", type_="check")
    op.drop_constraint("check_task_date_order", "tasks", type_="check")
    op.drop_constraint("check_task_estimated_hours", "tasks", type_="check")
    op.drop_constraint("check_task_type", "tasks", type_="check")
    op.drop_constraint("check_task_priority", "tasks", type_="check")
    op.drop_constraint("uq_tasks_project_number", "tasks", type_="unique")
    op.drop_index("idx_projects_active_lookup", table_name="projects")
    op.drop_index("idx_projects_status_lookup", table_name="projects")
    op.drop_constraint("check_project_next_task_number", "projects", type_="check")
    op.drop_constraint("check_project_date_order", "projects", type_="check")
    op.drop_constraint("check_project_priority", "projects", type_="check")
    op.drop_constraint("uq_projects_tenant_key", "projects", type_="unique")

    op.drop_column("daily_progress_logs", "deleted_at")
    op.drop_column("daily_progress_logs", "updated_at")
    op.drop_column("daily_progress_logs", "version")
    op.drop_column("daily_progress_logs", "work_date")
    op.drop_column("task_comments", "deleted_at")
    op.drop_column("task_comments", "updated_at")
    op.drop_column("task_comments", "version")
    op.drop_column("tasks", "archived_at")
    op.drop_column("tasks", "completed_at")
    op.drop_column("tasks", "updated_at")
    op.drop_column("tasks", "created_at")
    op.drop_column("tasks", "created_by_user_id")
    op.drop_column("tasks", "reporter_id")
    op.drop_column("tasks", "task_type")
    op.drop_column("tasks", "task_number")
    op.drop_column("projects", "archived_at")
    op.drop_column("projects", "updated_at")
    op.drop_column("projects", "created_at")
    op.drop_column("projects", "next_task_number")
    op.drop_column("projects", "project_key")
