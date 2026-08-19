"""repair databases upgraded through the pre-merge migration branch

Revision ID: 0016
Revises: 0015
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(connection, table_name: str, column: sa.Column) -> None:
    columns = {column_info["name"] for column_info in sa.inspect(connection).get_columns(table_name)}
    if column.name not in columns:
        op.add_column(table_name, column)


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())

    # The merged branch introduced these fields in its 0009 migration. Some
    # development databases reached 0015 through the other 0009 migration.
    for column in (
        sa.Column("failed_login_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    ):
        _add_column_if_missing(connection, "platform_admins", column)

    if "user_accounts" not in tables:
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
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["user_accounts.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "email", name="uq_tenant_user_email"),
            sa.UniqueConstraint("tenant_id", "id", name="uq_user_accounts_tenant_id"),
        )
        op.create_index("ix_user_accounts_tenant_id", "user_accounts", ["tenant_id"])
        op.create_index("ix_user_accounts_email", "user_accounts", ["email"])

    if "roles" not in tables:
        op.create_table(
            "roles",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role_code", sa.String(length=100), nullable=False),
            sa.Column("role_name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "role_code", name="uq_tenant_role_code"),
        )
        op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])

    if "user_roles" not in tables:
        op.create_table(
            "user_roles",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("assigned_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "role_id", name="uq_user_role"),
        )
        op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
        op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    if "user_sessions" not in tables:
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
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_by", sa.String(length=50), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("principal_type IN ('platform_admin', 'tenant_user')", name="check_user_sessions_principal_type"),
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

    # Copy legacy accounts without deleting the old table. Keeping it makes
    # rollback and older workers safe while the application moves to the new
    # account model.
    if "users" in tables:
        connection.execute(
            sa.text(
                """
                INSERT INTO user_accounts (
                    id, tenant_id, email, password_hash, display_name,
                    is_active, version, created_at, updated_at
                )
                SELECT user_id, tenant_id, email, password_hash, name,
                       status = 'Active', version, created_at, created_at
                FROM users
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO roles (id, tenant_id, role_code, role_name, description, is_system, is_active)
                SELECT uuid_generate_v4(), t.tenant_id,
                       upper(replace(t.role_name, ' ', '_')), t.role_name,
                       'Migrated legacy role', true, true
                FROM (SELECT DISTINCT tenant_id, role AS role_name FROM users) t
                ON CONFLICT (tenant_id, role_code) DO NOTHING
                """
            )
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO user_roles (id, user_id, role_id, assigned_by, is_active)
                SELECT uuid_generate_v4(), ua.id, r.id, NULL, true
                FROM users u
                JOIN user_accounts ua ON ua.id = u.user_id
                JOIN roles r ON r.tenant_id = u.tenant_id AND r.role_name = u.role
                ON CONFLICT (user_id, role_id) DO NOTHING
                """
            )
        )

    # Existing feature-branch tables still point at users. Retarget every
    # such FK while preserving its name and delete action.
    inspector = sa.inspect(connection)
    for table_name in inspector.get_table_names():
        for foreign_key in inspector.get_foreign_keys(table_name):
            if foreign_key.get("referred_table") != "users" or not foreign_key.get("name"):
                continue
            constrained = foreign_key["constrained_columns"]
            referred = ["tenant_id", "id"] if "tenant_id" in constrained else ["id"]
            op.drop_constraint(foreign_key["name"], table_name, type_="foreignkey")
            options = foreign_key.get("options") or {}
            op.create_foreign_key(
                foreign_key["name"],
                table_name,
                "user_accounts",
                constrained,
                referred,
                ondelete=options.get("ondelete"),
            )


def downgrade() -> None:
    raise NotImplementedError("The auth schema repair is not reversible without data loss")
