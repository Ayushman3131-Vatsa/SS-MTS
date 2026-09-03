"""Ensure full modify grants for Platform Admin role on all platform pages.

Revision ID: 0049
Revises: 0048
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0049"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO platform_role_page_access (id, role_id, page_id, access_level)
            SELECT uuid_generate_v4(), roles.id, pages.id, 'modify'
            FROM platform_roles AS roles
            CROSS JOIN pages
            WHERE roles.role_code = 'PLATFORM_ADMIN'
              AND pages.app_scope = 'platform'
              AND pages.is_active IS TRUE
            ON CONFLICT (role_id, page_id) DO UPDATE SET access_level = 'modify';
            """
        )
    )


def downgrade() -> None:
    pass
