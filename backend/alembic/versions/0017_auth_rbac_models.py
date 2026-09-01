"""add platform and tenant rbac permission models

Revision ID: 0017
Revises: 0016
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_roles_tenant_id", "roles", ["tenant_id", "id"])

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

    op.create_table(
        "platform_permissions",
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
        sa.UniqueConstraint("permission_code", name="uq_platform_permissions_code"),
    )
    op.create_index("ix_platform_permissions_permission_code", "platform_permissions", ["permission_code"])

    op.create_table(
        "tenant_permissions",
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
        sa.UniqueConstraint("permission_code", name="uq_tenant_permissions_code"),
    )
    op.create_index("ix_tenant_permissions_permission_code", "tenant_permissions", ["permission_code"])

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



def downgrade() -> None:
    op.drop_index("ix_tenant_role_permissions_permission_id", table_name="tenant_role_permissions")
    op.drop_index("ix_tenant_role_permissions_role_id", table_name="tenant_role_permissions")
    op.drop_index("ix_tenant_role_permissions_tenant_id", table_name="tenant_role_permissions")
    op.drop_table("tenant_role_permissions")
    op.drop_index("ix_platform_role_page_access_page_id", table_name="platform_role_page_access")
    op.drop_index("ix_platform_role_page_access_role_id", table_name="platform_role_page_access")
    op.drop_table("platform_role_page_access")
    op.drop_index("ix_platform_role_permissions_permission_id", table_name="platform_role_permissions")
    op.drop_index("ix_platform_role_permissions_role_id", table_name="platform_role_permissions")
    op.drop_table("platform_role_permissions")
    op.drop_index("ix_platform_user_roles_role_id", table_name="platform_user_roles")
    op.drop_index("ix_platform_user_roles_admin_id", table_name="platform_user_roles")
    op.drop_table("platform_user_roles")
    op.drop_index("ix_tenant_permissions_permission_code", table_name="tenant_permissions")
    op.drop_table("tenant_permissions")
    op.drop_index("ix_platform_permissions_permission_code", table_name="platform_permissions")
    op.drop_table("platform_permissions")
    op.drop_table("platform_roles")
    op.drop_constraint("uq_roles_tenant_id", "roles", type_="unique")
