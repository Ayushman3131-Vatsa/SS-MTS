"""Link tenant default roles to Tenant Administration and User Access offerings.

Revision ID: 0050
Revises: 0049
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0050"
down_revision: Union[str, None] = "0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    # 1. Map Tenant Administration roles to the offering UUID
    connection.execute(
        sa.text(
            """
            UPDATE platform_default_roles
            SET offering_id = (SELECT offering_id FROM offerings WHERE code = 'TENANT_ADMINISTRATION')
            WHERE module_scope = 'tenant_administration'
               OR (offering_id IS NULL AND role_code = 'TENANT_ADMIN');
            """
        )
    )

    # 2. Map User Access Management roles to the offering UUID
    connection.execute(
        sa.text(
            """
            UPDATE platform_default_roles
            SET offering_id = (SELECT offering_id FROM offerings WHERE code = 'USER_ACCESS_MANAGEMENT')
            WHERE module_scope = 'user_access_management';
            """
        )
    )

    # 3. Ensure a default USER_ACCESS_ADMIN role exists in platform_default_roles
    connection.execute(
        sa.text(
            """
            INSERT INTO platform_default_roles (id, role_code, role_name, description, offering_id, is_system, is_active, module_scope)
            SELECT
                uuid_generate_v4(),
                'USER_ACCESS_ADMIN',
                'User Access Administrator',
                'Administrator for tenant user provisioning, roles, and console permissions.',
                (SELECT offering_id FROM offerings WHERE code = 'USER_ACCESS_MANAGEMENT'),
                false,
                true,
                'user_access_management'
            WHERE NOT EXISTS (
                SELECT 1 FROM platform_default_roles
                WHERE role_code = 'USER_ACCESS_ADMIN'
                   OR (module_scope = 'user_access_management' AND role_code LIKE '%ADMIN%')
            );
            """
        )
    )

    # 4. Grant USER_ACCESS_ADMIN modify permissions on TENANT_USERS and TENANT_ROLES
    connection.execute(
        sa.text(
            """
            INSERT INTO platform_default_role_page_access (id, role_id, page_id, access_level)
            SELECT uuid_generate_v4(), roles.id, pages.id, 'modify'
            FROM platform_default_roles AS roles
            CROSS JOIN pages
            WHERE roles.role_code = 'USER_ACCESS_ADMIN'
              AND pages.page_code IN ('TENANT_USERS', 'TENANT_ROLES')
            ON CONFLICT (role_id, page_id) DO UPDATE SET access_level = 'modify';
            """
        )
    )


def downgrade() -> None:
    pass
