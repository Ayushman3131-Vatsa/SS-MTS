"""platform default role templates and page grants

Revision ID: 0041
Revises: 0040
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTIVITY_TYPES = (
    "'TENANT_CREATED', 'PLAN_CHANGED', 'TENANT_SUSPENDED', "
    "'TENANT_REACTIVATED', 'DATABASE_ALLOCATION_READY', "
    "'DATABASE_ALLOCATION_FAILED', 'TENANT_ACTIVATED', "
    "'OFFERING_GRANTED', 'OFFERING_SUSPENDED', 'OFFERING_RESUMED', "
    "'OFFERING_DEACTIVATED', 'OFFERING_EXPIRED', "
    "'OFFERING_CATALOG_CREATED', 'OFFERING_CATALOG_UPDATED', "
    "'OFFERING_CATALOG_ACTIVATED', 'OFFERING_CATALOG_DEACTIVATED', "
    "'OFFERING_CATALOG_DELETED', "
    "'DEFAULT_TEMPLATE_CREATED', 'DEFAULT_TEMPLATE_UPDATED', "
    "'DEFAULT_ROLE_CREATED', 'DEFAULT_ROLE_UPDATED', 'DEFAULT_ROLE_DELETED'"
)


def upgrade() -> None:
    op.create_table(
        "platform_default_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("offering_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("offerings.offering_id", ondelete="CASCADE"), nullable=True),
        sa.Column("role_code", sa.String(length=100), nullable=False),
        sa.Column("role_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("module_scope", sa.String(length=100), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("module_scope <> ''", name="check_platform_default_roles_module_scope"),
        sa.UniqueConstraint("offering_id", "role_code", name="uq_platform_default_roles_offering_code"),
    )
    op.create_index("ix_platform_default_roles_offering_id", "platform_default_roles", ["offering_id"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_platform_default_roles_core_code
        ON platform_default_roles (role_code)
        WHERE offering_id IS NULL
        """
    )

    op.create_table(
        "platform_default_role_page_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("platform_default_roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access_level", sa.String(length=10), nullable=False, server_default="none"),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("platform_admins.admin_id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("access_level IN ('none', 'view', 'modify')", name="check_platform_default_role_page_access_level"),
        sa.UniqueConstraint("role_id", "page_id", name="uq_platform_default_role_page"),
    )
    op.create_index("ix_platform_default_role_page_access_role_id", "platform_default_role_page_access", ["role_id"])
    op.create_index("ix_platform_default_role_page_access_page_id", "platform_default_role_page_access", ["page_id"])

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO pages (id, page_code, module, page_name, route, app_scope, is_active)
            VALUES (
                uuid_generate_v4(),
                'PLATFORM_DEFAULT_ROLES',
                'platform',
                'Default Roles',
                '/platform/default-roles',
                'platform',
                true
            )
            ON CONFLICT (page_code) DO UPDATE SET
                module = EXCLUDED.module,
                page_name = EXCLUDED.page_name,
                route = EXCLUDED.route,
                app_scope = EXCLUDED.app_scope,
                is_active = true
            """
        )
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO platform_role_page_access (id, role_id, page_id, access_level)
            SELECT uuid_generate_v4(), roles.id, pages.id, 'modify'
            FROM platform_roles AS roles
            CROSS JOIN pages
            WHERE roles.role_code = 'PLATFORM_ADMIN'
              AND pages.page_code = 'PLATFORM_DEFAULT_ROLES'
              AND pages.is_active IS TRUE
            ON CONFLICT (role_id, page_id) DO UPDATE SET access_level = 'modify'
            """
        )
    )

    connection.execute(
        sa.text(
            """
            INSERT INTO platform_default_roles (
                id, offering_id, role_code, role_name, description, module_scope, is_system, is_active, version
            )
            SELECT
                uuid_generate_v4(),
                NULL,
                'TENANT_ADMIN',
                'Tenant Admin',
                'Customer administrator for workspace users, roles, and configuration.',
                'CORE',
                true,
                true,
                1
            WHERE NOT EXISTS (
                SELECT 1 FROM platform_default_roles
                WHERE offering_id IS NULL AND role_code = 'TENANT_ADMIN'
            )
            """
        )
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO platform_default_role_page_access (id, role_id, page_id, access_level)
            SELECT uuid_generate_v4(), roles.id, pages.id, 'modify'
            FROM platform_default_roles AS roles
            CROSS JOIN pages
            WHERE roles.offering_id IS NULL
              AND roles.role_code = 'TENANT_ADMIN'
              AND pages.page_code IN (
                  'TENANT_OVERVIEW', 'TENANT_USERS', 'TENANT_ROLES', 'TENANT_CONFIGURATIONS'
              )
              AND pages.app_scope = 'tenant'
              AND pages.is_active IS TRUE
            ON CONFLICT (role_id, page_id) DO UPDATE SET access_level = 'modify'
            """
        )
    )

    connection.execute(
        sa.text(
            """
            INSERT INTO platform_default_roles (
                id, offering_id, role_code, role_name, description, module_scope, is_system, is_active, version
            )
            SELECT
                uuid_generate_v4(),
                offerings.offering_id,
                v.role_code,
                v.role_name,
                v.description,
                offerings.code,
                true,
                true,
                1
            FROM offerings
            CROSS JOIN (
                VALUES
                    (
                        'TASK_MANAGER',
                        'Task Manager',
                        'Create and manage projects, members, and tasks for the licensed module.'
                    ),
                    (
                        'TASK_VIEWER',
                        'Task Viewer',
                        'Read-only access to Task Management pages.'
                    )
            ) AS v(role_code, role_name, description)
            WHERE offerings.code = 'TASK_MANAGEMENT'
              AND NOT EXISTS (
                  SELECT 1 FROM platform_default_roles existing
                  WHERE existing.offering_id = offerings.offering_id
                    AND existing.role_code = v.role_code
              )
            """
        )
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO platform_default_role_page_access (id, role_id, page_id, access_level)
            SELECT uuid_generate_v4(), roles.id, pages.id,
                CASE WHEN roles.role_code = 'TASK_MANAGER' THEN 'modify' ELSE 'view' END
            FROM platform_default_roles AS roles
            JOIN offerings ON offerings.offering_id = roles.offering_id
            CROSS JOIN pages
            WHERE offerings.code = 'TASK_MANAGEMENT'
              AND roles.role_code IN ('TASK_MANAGER', 'TASK_VIEWER')
              AND pages.page_code IN (
                  'TENANT_TASK_MANAGEMENT', 'TENANT_TASK_PROJECTS', 'TENANT_MY_WORK', 'TENANT_TASKS'
              )
              AND pages.app_scope = 'tenant'
              AND pages.is_active IS TRUE
            ON CONFLICT (role_id, page_id) DO UPDATE SET
                access_level = EXCLUDED.access_level
            """
        )
    )

    op.execute("ALTER TABLE platform_activity_events DROP CONSTRAINT IF EXISTS check_platform_activity_events_type")
    op.create_check_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        f"event_type IN ({_ACTIVITY_TYPES})",
    )


def downgrade() -> None:
    op.execute("ALTER TABLE platform_activity_events DROP CONSTRAINT IF EXISTS check_platform_activity_events_type")
    op.create_check_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        "event_type IN ("
        "'TENANT_CREATED', 'PLAN_CHANGED', 'TENANT_SUSPENDED', "
        "'TENANT_REACTIVATED', 'DATABASE_ALLOCATION_READY', "
        "'DATABASE_ALLOCATION_FAILED', 'TENANT_ACTIVATED', "
        "'OFFERING_GRANTED', 'OFFERING_SUSPENDED', 'OFFERING_RESUMED', "
        "'OFFERING_DEACTIVATED', 'OFFERING_EXPIRED', "
        "'OFFERING_CATALOG_CREATED', 'OFFERING_CATALOG_UPDATED', "
        "'OFFERING_CATALOG_ACTIVATED', 'OFFERING_CATALOG_DEACTIVATED', "
        "'OFFERING_CATALOG_DELETED', "
        "'DEFAULT_TEMPLATE_CREATED', 'DEFAULT_TEMPLATE_UPDATED'"
        ")",
    )
    op.execute("DELETE FROM platform_role_page_access WHERE page_id IN (SELECT id FROM pages WHERE page_code = 'PLATFORM_DEFAULT_ROLES')")
    op.execute("DELETE FROM pages WHERE page_code = 'PLATFORM_DEFAULT_ROLES'")
    op.drop_table("platform_default_role_page_access")
    op.execute("DROP INDEX IF EXISTS uq_platform_default_roles_core_code")
    op.drop_index("ix_platform_default_roles_offering_id", table_name="platform_default_roles")
    op.drop_table("platform_default_roles")
