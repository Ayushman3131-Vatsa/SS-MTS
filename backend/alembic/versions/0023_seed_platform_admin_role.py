"""seed default Platform Admin role and page grants

Revision ID: 0023
Revises: 0022
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO platform_roles (
                id, role_code, role_name, description, is_system, is_active
            )
            VALUES (
                uuid_generate_v4(),
                'PLATFORM_ADMIN',
                'Platform Admin',
                'Full access to the platform console',
                true,
                true
            )
            ON CONFLICT (role_code) DO UPDATE SET
                role_name = EXCLUDED.role_name,
                is_system = true,
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
              AND pages.app_scope = 'platform'
              AND pages.is_active IS TRUE
            ON CONFLICT (role_id, page_id) DO UPDATE SET access_level = 'modify'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO platform_user_roles (id, admin_id, role_id, is_active)
            SELECT uuid_generate_v4(), admins.admin_id, roles.id, true
            FROM platform_admins AS admins
            CROSS JOIN platform_roles AS roles
            WHERE roles.role_code = 'PLATFORM_ADMIN'
              AND NOT EXISTS (
                  SELECT 1
                  FROM platform_user_roles AS assigned
                  WHERE assigned.admin_id = admins.admin_id
                    AND assigned.role_id = roles.id
              )
            """
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM platform_roles WHERE role_code = 'PLATFORM_ADMIN' AND is_system IS TRUE")
    )
