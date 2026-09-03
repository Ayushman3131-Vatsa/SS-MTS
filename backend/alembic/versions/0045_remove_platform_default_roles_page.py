"""remove platform default roles page entry

Revision ID: 0045
Revises: 0044
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            DELETE FROM platform_role_page_access
            WHERE page_id IN (
                SELECT id FROM pages WHERE page_code = 'PLATFORM_DEFAULT_ROLES'
            )
            """
        )
    )
    connection.execute(
        sa.text(
            """
            DELETE FROM pages
            WHERE page_code = 'PLATFORM_DEFAULT_ROLES'
            """
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO pages (
                id,
                page_code,
                module,
                page_name,
                route,
                app_scope,
                offering_code,
                is_active,
                created_at,
                updated_at
            ) VALUES (
                gen_random_uuid(),
                'PLATFORM_DEFAULT_ROLES',
                'platform_administration',
                'Default Roles',
                '/platform/default-roles',
                'platform',
                NULL,
                TRUE,
                NOW(),
                NOW()
            )
            ON CONFLICT (page_code) DO NOTHING
            """
        )
    )
