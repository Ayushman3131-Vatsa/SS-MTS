"""Use Tenant Admin for entitlement access and remove Dummy offering.

Revision ID: 0052
Revises: 0051
Create Date: 2026-09-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()

    # DUMMY is local placeholder catalog data, not a deployable offering.
    for statement in (
        """
        DELETE FROM tenant_offering_entitlements
        WHERE offering_id IN (SELECT offering_id FROM offerings WHERE code = 'DUMMY')
        """,
        """
        DELETE FROM config_categories
        WHERE offering_id IN (SELECT offering_id FROM offerings WHERE code = 'DUMMY')
        """,
        """
        DELETE FROM platform_default_roles
        WHERE offering_id IN (SELECT offering_id FROM offerings WHERE code = 'DUMMY')
        """,
        "DELETE FROM pages WHERE offering_code = 'DUMMY'",
        "DELETE FROM offerings WHERE code = 'DUMMY'",
    ):
        connection.execute(sa.text(statement))

    # TENANT_ADMIN is authoritative for every core page and every page covered
    # by a currently effective tenant entitlement.
    connection.execute(
        sa.text(
            """
            INSERT INTO role_page_access (id, role_id, page_id, access_level)
            SELECT uuid_generate_v4(), roles.id, pages.id, 'modify'
            FROM roles
            JOIN pages ON pages.app_scope = 'tenant' AND pages.is_active IS TRUE
            WHERE roles.role_code = 'TENANT_ADMIN'
              AND roles.is_active IS TRUE
              AND (
                    pages.page_code IN (
                        'TENANT_OVERVIEW', 'TENANT_USERS',
                        'TENANT_ROLES', 'TENANT_CONFIGURATIONS'
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM tenant_offering_entitlements entitlements
                        JOIN offerings
                          ON offerings.offering_id = entitlements.offering_id
                        WHERE entitlements.tenant_id = roles.tenant_id
                          AND entitlements.status = 'ACTIVE'
                          AND entitlements.starts_at <= NOW()
                          AND (
                              entitlements.ends_at IS NULL
                              OR entitlements.ends_at > NOW()
                          )
                          AND offerings.code = pages.offering_code
                    )
              )
            ON CONFLICT (role_id, page_id)
            DO UPDATE SET access_level = 'modify', updated_at = NOW();
            """
        )
    )

    connection.execute(
        sa.text(
            """
            UPDATE role_page_access access
            SET access_level = 'none', updated_at = NOW()
            FROM roles, pages
            WHERE access.role_id = roles.id
              AND access.page_id = pages.id
              AND roles.role_code = 'TENANT_ADMIN'
              AND pages.app_scope = 'tenant'
              AND pages.offering_code IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM tenant_offering_entitlements entitlements
                  JOIN offerings
                    ON offerings.offering_id = entitlements.offering_id
                  WHERE entitlements.tenant_id = roles.tenant_id
                    AND entitlements.status = 'ACTIVE'
                    AND entitlements.starts_at <= NOW()
                    AND (
                        entitlements.ends_at IS NULL
                        OR entitlements.ends_at > NOW()
                    )
                    AND offerings.code = pages.offering_code
              );
            """
        )
    )


def downgrade() -> None:
    # Deleted placeholder catalog data is intentionally not recreated.
    pass
