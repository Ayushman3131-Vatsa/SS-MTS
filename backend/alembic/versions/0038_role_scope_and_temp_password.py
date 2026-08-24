"""add role module scope, platform password reset, unique employee ids

Revision ID: 0038
Revises: 0037
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "platform_admins",
        sa.Column("force_pw_reset", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("roles", sa.Column("module_scope", sa.String(length=100), nullable=True))
    op.add_column("platform_roles", sa.Column("module_scope", sa.String(length=100), nullable=True))
    op.create_index(
        "uq_user_accounts_tenant_employee_id",
        "user_accounts",
        ["tenant_id", "employee_id"],
        unique=True,
        postgresql_where=sa.text("employee_id IS NOT NULL"),
    )
    op.create_index(
        "uq_platform_admins_employee_id",
        "platform_admins",
        ["employee_id"],
        unique=True,
        postgresql_where=sa.text("employee_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_platform_admins_employee_id", table_name="platform_admins")
    op.drop_index("uq_user_accounts_tenant_employee_id", table_name="user_accounts")
    op.drop_column("platform_roles", "module_scope")
    op.drop_column("roles", "module_scope")
    op.drop_column("platform_admins", "force_pw_reset")
