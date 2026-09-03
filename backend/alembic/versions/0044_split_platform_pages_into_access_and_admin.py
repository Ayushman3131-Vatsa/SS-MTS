"""split platform pages into user_access_management and platform_administration

Revision ID: 0044
Revises: 0043a
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0044"
down_revision: Union[str, None] = "0043a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET module = 'user_access_management'
            WHERE app_scope = 'platform'
              AND page_code IN ('PLATFORM_USERS', 'PLATFORM_ROLES')
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET module = 'platform_administration'
            WHERE app_scope = 'platform'
              AND page_code IN (
                  'PLATFORM_DASHBOARD',
                  'PLATFORM_TENANTS',
                  'PLATFORM_TENANT_REGISTER',
                  'PLATFORM_OFFERINGS',
                  'PLATFORM_DEFAULT_TEMPLATES',
                  'PLATFORM_DEFAULT_ROLES'
              )
            """
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET module = 'platform'
            WHERE app_scope = 'platform'
              AND page_code IN (
                  'PLATFORM_USERS',
                  'PLATFORM_ROLES',
                  'PLATFORM_DASHBOARD',
                  'PLATFORM_TENANTS',
                  'PLATFORM_TENANT_REGISTER',
                  'PLATFORM_OFFERINGS',
                  'PLATFORM_DEFAULT_TEMPLATES',
                  'PLATFORM_DEFAULT_ROLES'
              )
            """
        )
    )
