"""migrate to user_accounts sessions roles and hrms models

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_ROLES = (
    ("TENANT_ADMIN", "Tenant Admin"),
    ("PROJECT_MANAGER", "Project Manager"),
    ("EMPLOYEE", "Employee"),
)


def upgrade() -> None:
    # --- platform admin lockout fields (replaces auth_rate_limits for accounts) ---
    op.add_column(
        "platform_admins",
        sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "platform_admins",
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "platform_admins",
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- user_accounts ---
    op.create_table(
        "user_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("force_pw_reset", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_tenant_user_email"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_user_accounts_tenant_id"),
    )
    op.create_index("ix_user_accounts_tenant_id", "user_accounts", ["tenant_id"])
    op.create_index("ix_user_accounts_email", "user_accounts", ["email"])

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_code", sa.String(length=100), nullable=False),
        sa.Column("role_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "role_code", name="uq_tenant_role_code"),
    )
    op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])

    op.create_table(
        "user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    # Seed system roles per existing tenant
    conn = op.get_bind()
    tenants = conn.execute(sa.text("SELECT tenant_id FROM tenants")).fetchall()
    role_id_by_tenant_and_name: dict[tuple, object] = {}
    for (tenant_id,) in tenants:
        for role_code, role_name in SYSTEM_ROLES:
            role_id = conn.execute(
                sa.text(
                    """
                    INSERT INTO roles (id, tenant_id, role_code, role_name, description, is_system, is_active)
                    VALUES (uuid_generate_v4(), :tenant_id, :role_code, :role_name, :description, true, true)
                    RETURNING id
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "role_code": role_code,
                    "role_name": role_name,
                    "description": f"System role: {role_name}",
                },
            ).scalar_one()
            role_id_by_tenant_and_name[(tenant_id, role_name)] = role_id

    # Migrate users → user_accounts (+ user_roles)
    old_users = conn.execute(
        sa.text(
            """
            SELECT tenant_id, user_id, name, email, password_hash, role, created_by_user_id,
                   status, version, created_at
            FROM users
            """
        )
    ).fetchall()
    for row in old_users:
        (
            tenant_id,
            user_id,
            name,
            email,
            password_hash,
            role_name,
            created_by_user_id,
            status,
            version,
            created_at,
        ) = row
        conn.execute(
            sa.text(
                """
                INSERT INTO user_accounts (
                    id, tenant_id, email, password_hash, display_name, created_by_user_id,
                    is_active, version, created_at, updated_at
                ) VALUES (
                    :id, :tenant_id, :email, :password_hash, :display_name, :created_by_user_id,
                    :is_active, :version, :created_at, :created_at
                )
                """
            ),
            {
                "id": user_id,
                "tenant_id": tenant_id,
                "email": email,
                "password_hash": password_hash,
                "display_name": name,
                "created_by_user_id": created_by_user_id,
                "is_active": status == "Active",
                "version": version,
                "created_at": created_at,
            },
        )
        role_id = role_id_by_tenant_and_name.get((tenant_id, role_name))
        if role_id is not None:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO user_roles (id, user_id, role_id, assigned_by, is_active)
                    VALUES (uuid_generate_v4(), :user_id, :role_id, :assigned_by, true)
                    """
                ),
                {
                    "user_id": user_id,
                    "role_id": role_id,
                    "assigned_by": created_by_user_id,
                },
            )

    # Retarget project/task authorship FKs from users → user_accounts
    for table, constraint in (
        ("projects", "fk_project_pm"),
        ("projects", "fk_project_dm"),
        ("tasks", "fk_task_assignee"),
        ("tasks", "fk_task_tech_lead"),
        ("tasks", "fk_task_func_lead"),
        ("task_comments", "fk_comment_author"),
        ("daily_progress_logs", "fk_log_author"),
    ):
        op.drop_constraint(constraint, table, type_="foreignkey")

    op.create_foreign_key(
        "fk_project_pm",
        "projects",
        "user_accounts",
        ["tenant_id", "pm_id"],
        ["tenant_id", "id"],
    )
    op.create_foreign_key(
        "fk_project_dm",
        "projects",
        "user_accounts",
        ["tenant_id", "dm_id"],
        ["tenant_id", "id"],
    )
    op.create_foreign_key(
        "fk_task_assignee",
        "tasks",
        "user_accounts",
        ["tenant_id", "assignee_id"],
        ["tenant_id", "id"],
    )
    op.create_foreign_key(
        "fk_task_tech_lead",
        "tasks",
        "user_accounts",
        ["tenant_id", "technical_lead_id"],
        ["tenant_id", "id"],
    )
    op.create_foreign_key(
        "fk_task_func_lead",
        "tasks",
        "user_accounts",
        ["tenant_id", "functional_lead_id"],
        ["tenant_id", "id"],
    )
    op.create_foreign_key(
        "fk_comment_author",
        "task_comments",
        "user_accounts",
        ["tenant_id", "commented_by_user_id"],
        ["tenant_id", "id"],
    )
    op.create_foreign_key(
        "fk_log_author",
        "daily_progress_logs",
        "user_accounts",
        ["tenant_id", "updated_by_user_id"],
        ["tenant_id", "id"],
    )

    # --- user_sessions (replaces browser_sessions) ---
    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("principal_type", sa.String(length=32), nullable=False),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("device_label", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(length=50), nullable=True),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "principal_type IN ('platform_admin', 'tenant_user')",
            name="check_user_sessions_principal_type",
        ),
        sa.CheckConstraint(
            "(principal_type = 'platform_admin' AND tenant_id IS NULL AND user_id IS NULL) OR "
            "(principal_type = 'tenant_user' AND tenant_id IS NOT NULL AND user_id IS NOT NULL)",
            name="check_user_sessions_tenant_context",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_user_sessions_token_hash"),
    )
    op.create_index("ix_user_sessions_principal", "user_sessions", ["principal_type", "principal_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])
    op.create_index("ix_user_sessions_tenant_user", "user_sessions", ["tenant_id", "user_id"])
    op.create_index("ix_user_sessions_tenant_id", "user_sessions", ["tenant_id"])
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    conn.execute(
        sa.text(
            """
            INSERT INTO user_sessions (
                id, token_hash, csrf_token_hash, principal_type, principal_id,
                tenant_id, user_id, created_at, expires_at, revoked_at, last_seen_at
            )
            SELECT
                session_id,
                token_hash,
                csrf_token_hash,
                principal_type,
                principal_id,
                tenant_id,
                CASE WHEN principal_type = 'tenant_user' THEN principal_id ELSE NULL END,
                created_at,
                expires_at,
                revoked_at,
                last_seen_at
            FROM browser_sessions
            """
        )
    )

    op.drop_table("browser_sessions")
    op.drop_table("auth_rate_limits")
    op.drop_table("users")

    # --- remaining HRMS / RBAC tables via metadata ---
    # Circular FKs (user_accounts <-> employees <-> candidates) break
    # sorted_tables ordering, so create bodies first, then foreign keys.
    from sqlalchemy.schema import AddConstraint, CreateTable

    from app.common.db.base import Base
    import app.db.all_models  # noqa: F401

    already = {
        "user_accounts",
        "roles",
        "user_roles",
        "user_sessions",
        "platform_admins",
        "tenants",
        "projects",
        "tasks",
        "task_comments",
        "daily_progress_logs",
        "audit_logs",
        "offerings",
        "subscription_plans",
        "tenant_subscriptions",
        "tenant_database_allocations",
        "tenant_offerings",
        "platform_activity_events",
    }

    # Prefer a stable dependency-friendly order; anything else follows alphabetically.
    preferred = [
        "pages",
        "tenant_modules",
        "departments",
        "work_locations",
        "designations",
        "documents",
        "candidates",
        "candidate_personal_details",
        "candidate_compensation",
        "candidate_education",
        "candidate_emergency_contacts",
        "candidate_employment_history",
        "candidate_status_log",
        "candidate_uploaded_documents",
        "employees",
        "employee_personal_details",
        "employee_bank_details",
        "employee_compensation",
        "employee_compensation_components",
        "employee_dependents",
        "employee_education",
        "employee_emergency_contacts",
        "employee_employment_details",
        "employee_employment_history",
        "employee_status_log",
        "employee_uploaded_documents",
        "employee_ytd_balances",
        "exit_interviews",
        "salary_structures",
        "salary_structure_components",
        "pay_calendar",
        "payroll_runs",
        "payroll_records",
        "payroll_record_components",
        "role_page_access",
        "password_reset_tokens",
        "email_log",
    ]

    pending = [name for name in Base.metadata.tables if name not in already]
    ordered = [name for name in preferred if name in pending]
    ordered.extend(sorted(name for name in pending if name not in ordered))

    created = []
    for name in ordered:
        table = Base.metadata.tables[name]
        # Ensure any PostgreSQL ENUM types referenced by columns exist first.
        for column in table.columns:
            col_type = column.type
            if hasattr(col_type, "create") and getattr(col_type, "native_enum", False):
                col_type.create(conn, checkfirst=True)
        conn.execute(CreateTable(table, include_foreign_key_constraints=[]))
        created.append(table)

    for table in created:
        for index in table.indexes:
            index.create(bind=conn)
        for fk in table.foreign_key_constraints:
            conn.execute(AddConstraint(fk))


def downgrade() -> None:
    raise NotImplementedError("Downgrade from user_accounts / HRMS schema is not supported")
