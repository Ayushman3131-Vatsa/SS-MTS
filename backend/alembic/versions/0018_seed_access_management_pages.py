"""seed access management page catalog entries

Revision ID: 0018
Revises: 0017
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PLATFORM_PAGES = (
    ("PLATFORM_DASHBOARD", "platform", "Dashboard", "/platform", "platform"),
    ("PLATFORM_TENANTS", "platform", "All Tenants", "/platform/tenants", "platform"),
    ("PLATFORM_TENANT_REGISTER", "platform", "Register Tenant", "/platform/tenants/register", "platform"),
    ("PLATFORM_USERS", "platform", "Users", "/platform/users", "platform"),
    ("PLATFORM_ROLES", "platform", "Roles & Permissions", "/platform/roles", "platform"),
    ("PLATFORM_OFFERINGS", "platform", "Offerings", "/platform/offerings", "platform"),
    ("PLATFORM_DEFAULT_TEMPLATES", "platform", "Default Templates", "/platform/default-templates", "platform"),
)

TENANT_PAGES = (
    ("TENANT_OVERVIEW", "workspace", "Overview", "/app/overview", "tenant"),
    ("TENANT_USERS", "workspace", "Users", "/app/users", "tenant"),
    ("TENANT_ROLES", "workspace", "Roles & Permissions", "/app/roles", "tenant"),
    ("TENANT_CONFIGURATIONS", "workspace", "Configurations", "/app/configurations", "tenant"),
    ("TENANT_TASK_MANAGEMENT", "task_management", "Task Management", "/app/task-management", "tenant"),
    ("TENANT_TASK_PROJECTS", "task_management", "Projects", "/app/task-management/projects", "tenant"),
    ("TENANT_MY_WORK", "task_management", "My Work", "/app/task-management/my-work", "tenant"),
    ("TENANT_TASKS", "task_management", "All Tasks", "/app/task-management/tasks", "tenant"),
)


def upgrade() -> None:
    connection = op.get_bind()
    for page_code, module, page_name, route, app_scope in (*PLATFORM_PAGES, *TENANT_PAGES):
        connection.execute(
            sa.text(
                """
                INSERT INTO pages (id, page_code, module, page_name, route, app_scope, is_active)
                VALUES (uuid_generate_v4(), :page_code, :module, :page_name, :route, :app_scope, true)
                ON CONFLICT (page_code) DO UPDATE SET
                    module = EXCLUDED.module,
                    page_name = EXCLUDED.page_name,
                    route = EXCLUDED.route,
                    app_scope = EXCLUDED.app_scope,
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


def downgrade() -> None:
    connection = op.get_bind()
    page_codes = [page[0] for page in (*PLATFORM_PAGES, *TENANT_PAGES)]
    connection.execute(
        sa.text("DELETE FROM pages WHERE page_code = ANY(:page_codes)"),
        {"page_codes": page_codes},
    )
