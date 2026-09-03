"""repair access-control tables skipped by stamped migrations

Revision ID: 0020a
Revises: 0020

Some development databases were stamped through the pre-merge auth/RBAC
migrations without receiving the metadata-created tables from 0009 or the
tables from 0017.  The next migration (0021) reads ``pages`` immediately, so
those databases could never advance to the current head.

This bridge is deliberately idempotent: healthy databases keep their existing
tables and data, while drifted databases receive the schema and seed rows that
must exist at revision 0020.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0020a"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PAGES = (
    ("PLATFORM_DASHBOARD", "platform", "Dashboard", "/platform", "platform", None),
    ("PLATFORM_TENANTS", "platform", "All Tenants", "/platform/tenants", "platform", None),
    (
        "PLATFORM_TENANT_REGISTER",
        "platform",
        "Register Tenant",
        "/platform/tenants/register",
        "platform",
        None,
    ),
    ("PLATFORM_USERS", "platform", "Users", "/platform/users", "platform", None),
    (
        "PLATFORM_ROLES",
        "platform",
        "Roles & Permissions",
        "/platform/roles",
        "platform",
        None,
    ),
    ("PLATFORM_OFFERINGS", "platform", "Offerings", "/platform/offerings", "platform", None),
    (
        "PLATFORM_DEFAULT_TEMPLATES",
        "platform",
        "Default Templates",
        "/platform/default-templates",
        "platform",
        None,
    ),
    ("TENANT_OVERVIEW", "workspace", "Overview", "/app/overview", "tenant", None),
    ("TENANT_USERS", "workspace", "Users", "/app/users", "tenant", None),
    (
        "TENANT_ROLES",
        "workspace",
        "Roles & Permissions",
        "/app/roles",
        "tenant",
        None,
    ),
    (
        "TENANT_CONFIGURATIONS",
        "workspace",
        "Configurations",
        "/app/configurations",
        "tenant",
        None,
    ),
    (
        "TENANT_TASK_MANAGEMENT",
        "task_management",
        "Task Management",
        "/app/task-management",
        "tenant",
        "TASK_MANAGEMENT",
    ),
    (
        "TENANT_TASK_PROJECTS",
        "task_management",
        "Projects",
        "/app/task-management/projects",
        "tenant",
        "TASK_MANAGEMENT",
    ),
    (
        "TENANT_MY_WORK",
        "task_management",
        "My Work",
        "/app/task-management/my-work",
        "tenant",
        "TASK_MANAGEMENT",
    ),
    (
        "TENANT_TASKS",
        "task_management",
        "All Tasks",
        "/app/task-management/tasks",
        "tenant",
        "TASK_MANAGEMENT",
    ),
    (
        "CORE_HR_EMPLOYEES",
        "core_hr",
        "Employees",
        "/app/modules/core-hr",
        "tenant",
        "CORE_HR",
    ),
    ("PAYROLL_RUNS", "payroll", "Payroll", "/app/modules/payroll", "tenant", "PAYROLL"),
    (
        "LEAVE_REQUESTS",
        "leave",
        "Leave",
        "/app/modules/leave-management",
        "tenant",
        "LEAVE_MANAGEMENT",
    ),
)


def _table_names(connection: sa.Connection) -> set[str]:
    return set(sa.inspect(connection).get_table_names())


def _has_constraint(connection: sa.Connection, table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(connection)
    constraints = inspector.get_unique_constraints(table_name)
    return any(item.get("name") == constraint_name for item in constraints)


def _create_pages() -> None:
    op.create_table(
        "pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_code", sa.String(length=50), nullable=False),
        sa.Column("module", sa.String(length=100), nullable=False),
        sa.Column("page_name", sa.String(length=255), nullable=False),
        sa.Column("route", sa.String(length=512), nullable=False),
        sa.Column("app_scope", sa.String(length=10), nullable=False, server_default="tenant"),
        sa.Column("offering_code", sa.String(length=50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("page_code", name="uq_pages_page_code"),
    )
    op.create_index("ix_pages_page_code", "pages", ["page_code"])
    op.create_index("ix_pages_offering_code", "pages", ["offering_code"])


def _create_role_page_access() -> None:
    op.create_table(
        "role_page_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_level", sa.String(length=10), nullable=False, server_default="none"),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "page_id", name="uq_role_page"),
    )
    op.create_index("ix_role_page_access_role_id", "role_page_access", ["role_id"])
    op.create_index("ix_role_page_access_page_id", "role_page_access", ["page_id"])


def _create_platform_roles() -> None:
    op.create_table(
        "platform_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_code", sa.String(length=100), nullable=False),
        sa.Column("role_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_code", name="uq_platform_roles_role_code"),
    )


def _create_permissions(table_name: str, constraint_name: str, index_name: str) -> None:
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_code", sa.String(length=150), nullable=False),
        sa.Column("module", sa.String(length=100), nullable=False),
        sa.Column("resource", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("permission_code", name=constraint_name),
    )
    op.create_index(index_name, table_name, ["permission_code"])


def _create_platform_user_roles() -> None:
    op.create_table(
        "platform_user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("admin_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["platform_admins.admin_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_by"], ["platform_admins.admin_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by"], ["platform_admins.admin_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["role_id"], ["platform_roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("admin_id", "role_id", name="uq_platform_user_role"),
    )
    op.create_index("ix_platform_user_roles_admin_id", "platform_user_roles", ["admin_id"])
    op.create_index("ix_platform_user_roles_role_id", "platform_user_roles", ["role_id"])


def _create_platform_role_permissions() -> None:
    op.create_table(
        "platform_role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["granted_by"], ["platform_admins.admin_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["permission_id"], ["platform_permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["platform_roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_id", name="uq_platform_role_permission"),
    )
    op.create_index("ix_platform_role_permissions_role_id", "platform_role_permissions", ["role_id"])
    op.create_index("ix_platform_role_permissions_permission_id", "platform_role_permissions", ["permission_id"])


def _create_platform_role_page_access() -> None:
    op.create_table(
        "platform_role_page_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("access_level", sa.String(length=10), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["page_id"], ["pages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["platform_roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["platform_admins.admin_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "page_id", name="uq_platform_role_page"),
    )
    op.create_index("ix_platform_role_page_access_role_id", "platform_role_page_access", ["role_id"])
    op.create_index("ix_platform_role_page_access_page_id", "platform_role_page_access", ["page_id"])


def _create_tenant_role_permissions() -> None:
    op.create_table(
        "tenant_role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["granted_by"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["permission_id"], ["tenant_permissions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "role_id"],
            ["roles.tenant_id", "roles.id"],
            ondelete="CASCADE",
            name="fk_tenant_role_permissions_role_tenant",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "role_id", "permission_id", name="uq_tenant_role_permission"),
    )
    op.create_index("ix_tenant_role_permissions_tenant_id", "tenant_role_permissions", ["tenant_id"])
    op.create_index("ix_tenant_role_permissions_role_id", "tenant_role_permissions", ["role_id"])
    op.create_index("ix_tenant_role_permissions_permission_id", "tenant_role_permissions", ["permission_id"])


def upgrade() -> None:
    connection = op.get_bind()
    tables = _table_names(connection)

    if "pages" not in tables:
        _create_pages()
    if "role_page_access" not in tables:
        _create_role_page_access()

    if not _has_constraint(connection, "roles", "uq_roles_tenant_id"):
        op.create_unique_constraint("uq_roles_tenant_id", "roles", ["tenant_id", "id"])

    tables = _table_names(connection)
    if "platform_roles" not in tables:
        _create_platform_roles()
    if "platform_permissions" not in tables:
        _create_permissions(
            "platform_permissions",
            "uq_platform_permissions_code",
            "ix_platform_permissions_permission_code",
        )
    if "tenant_permissions" not in tables:
        _create_permissions(
            "tenant_permissions",
            "uq_tenant_permissions_code",
            "ix_tenant_permissions_permission_code",
        )

    tables = _table_names(connection)
    if "platform_user_roles" not in tables:
        _create_platform_user_roles()
    if "platform_role_permissions" not in tables:
        _create_platform_role_permissions()
    if "platform_role_page_access" not in tables:
        _create_platform_role_page_access()
    if "tenant_role_permissions" not in tables:
        _create_tenant_role_permissions()

    for page_code, module, page_name, route, app_scope, offering_code in PAGES:
        connection.execute(
            sa.text(
                """
                INSERT INTO pages (
                    id, page_code, module, page_name, route, app_scope, offering_code, is_active
                )
                VALUES (
                    uuid_generate_v4(), :page_code, :module, :page_name, :route,
                    :app_scope, :offering_code, true
                )
                ON CONFLICT (page_code) DO UPDATE SET
                    module = EXCLUDED.module,
                    page_name = EXCLUDED.page_name,
                    route = EXCLUDED.route,
                    app_scope = EXCLUDED.app_scope,
                    offering_code = EXCLUDED.offering_code,
                    is_active = true
                """
            ),
            {
                "page_code": page_code,
                "module": module,
                "page_name": page_name,
                "route": route,
                "app_scope": app_scope,
                "offering_code": offering_code,
            },
        )


def downgrade() -> None:
    # This is a drift repair. Removing objects that may predate the bridge
    # would be destructive and would make a healthy database unhealthy.
    pass
