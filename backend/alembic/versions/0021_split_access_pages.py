"""split combined Access pages into Users and Roles & Permissions

Revision ID: 0021
Revises: 0020a
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0021"
down_revision: Union[str, None] = "0020a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SPLIT_PAGES = (
    ("PLATFORM_USERS", "platform", "Users", "/platform/users", "platform", "PLATFORM_ACCESS"),
    ("PLATFORM_ROLES", "platform", "Roles & Permissions", "/platform/roles", "platform", "PLATFORM_ACCESS"),
    ("TENANT_USERS", "workspace", "Users", "/app/users", "tenant", "TENANT_ACCESS"),
    ("TENANT_ROLES", "workspace", "Roles & Permissions", "/app/roles", "tenant", "TENANT_ACCESS"),
)


def upgrade() -> None:
    connection = op.get_bind()
    for page_code, module, page_name, route, app_scope, _source in SPLIT_PAGES:
        connection.execute(
            sa.text(
                """
                INSERT INTO pages (
                    id, page_code, module, page_name, route, app_scope, offering_code, is_active
                )
                VALUES (
                    uuid_generate_v4(), :page_code, :module, :page_name, :route,
                    :app_scope, NULL, true
                )
                ON CONFLICT (page_code) DO UPDATE SET
                    module = EXCLUDED.module,
                    page_name = EXCLUDED.page_name,
                    route = EXCLUDED.route,
                    app_scope = EXCLUDED.app_scope,
                    offering_code = NULL,
                    is_active = true
                """
            ),
            {
                "page_code": page_code,
                "module": module,
                "page_name": page_name,
                "route": route,
                "app_scope": app_scope,
            },
        )

    connection.execute(
        sa.text(
            """
            INSERT INTO platform_role_page_access (id, role_id, page_id, access_level, updated_by)
            SELECT uuid_generate_v4(), access.role_id, new_page.id, access.access_level, access.updated_by
            FROM platform_role_page_access AS access
            JOIN pages AS old_page ON old_page.id = access.page_id
            JOIN pages AS new_page ON new_page.page_code IN ('PLATFORM_USERS', 'PLATFORM_ROLES')
            WHERE old_page.page_code = 'PLATFORM_ACCESS'
            ON CONFLICT (role_id, page_id) DO NOTHING
            """
        )
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO role_page_access (id, role_id, page_id, access_level, updated_by)
            SELECT uuid_generate_v4(), access.role_id, new_page.id, access.access_level, access.updated_by
            FROM role_page_access AS access
            JOIN pages AS old_page ON old_page.id = access.page_id
            JOIN pages AS new_page ON new_page.page_code IN ('TENANT_USERS', 'TENANT_ROLES')
            WHERE old_page.page_code = 'TENANT_ACCESS'
            ON CONFLICT (role_id, page_id) DO NOTHING
            """
        )
    )
    connection.execute(
        sa.text("DELETE FROM pages WHERE page_code IN ('PLATFORM_ACCESS', 'TENANT_ACCESS')")
    )


def downgrade() -> None:
    connection = op.get_bind()
    for page_code, module, page_name, route, app_scope, source in (
        ("PLATFORM_ACCESS", "platform", "Access", "/platform/access", "platform", None),
        ("TENANT_ACCESS", "workspace", "Access", "/app/access", "tenant", None),
    ):
        connection.execute(
            sa.text(
                """
                INSERT INTO pages (id, page_code, module, page_name, route, app_scope, is_active)
                VALUES (uuid_generate_v4(), :page_code, :module, :page_name, :route, :app_scope, true)
                ON CONFLICT (page_code) DO UPDATE SET is_active = true
                """
            ),
            {
                "page_code": page_code,
                "module": module,
                "page_name": page_name,
                "route": route,
                "app_scope": app_scope,
            },
        )
    connection.execute(
        sa.text(
            "DELETE FROM pages WHERE page_code IN ('PLATFORM_USERS', 'PLATFORM_ROLES', 'TENANT_USERS', 'TENANT_ROLES')"
        )
    )
