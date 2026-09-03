"""split workspace module into user_access_management and tenant_administration

Revision ID: 0043a
Revises: 0043
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0043a"
down_revision: Union[str, None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET module = 'user_access_management'
            WHERE page_code IN ('TENANT_USERS', 'TENANT_ROLES')
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET module = 'tenant_administration'
            WHERE page_code IN ('TENANT_OVERVIEW', 'TENANT_CONFIGURATIONS')
            """
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET module = 'workspace'
            WHERE page_code IN (
                'TENANT_USERS',
                'TENANT_ROLES',
                'TENANT_OVERVIEW',
                'TENANT_CONFIGURATIONS'
            )
            """
        )
    )
