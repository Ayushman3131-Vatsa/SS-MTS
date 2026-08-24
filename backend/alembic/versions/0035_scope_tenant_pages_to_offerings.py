"""deactivate legacy tenant pages and align offering codes

Revision ID: 0035
Revises: 0034
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CANONICAL_TENANT_PAGE_CODES = (
    "TENANT_OVERVIEW",
    "TENANT_USERS",
    "TENANT_ROLES",
    "TENANT_CONFIGURATIONS",
    "TENANT_TASK_MANAGEMENT",
    "TENANT_TASK_PROJECTS",
    "TENANT_MY_WORK",
    "TENANT_TASKS",
    "CORE_HR_EMPLOYEES",
    "PAYROLL_RUNS",
    "LEAVE_REQUESTS",
)


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET is_active = false
            WHERE app_scope = 'tenant'
              AND page_code != ALL(:page_codes)
            """
        ),
        {"page_codes": list(CANONICAL_TENANT_PAGE_CODES)},
    )
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET offering_code = 'TASK_MANAGEMENT', is_active = true
            WHERE app_scope = 'tenant'
              AND page_code IN (
                'TENANT_TASK_MANAGEMENT',
                'TENANT_TASK_PROJECTS',
                'TENANT_MY_WORK',
                'TENANT_TASKS'
              )
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET offering_code = 'CORE_HR', is_active = true
            WHERE page_code = 'CORE_HR_EMPLOYEES'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET offering_code = 'PAYROLL', is_active = true
            WHERE page_code = 'PAYROLL_RUNS'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET offering_code = 'LEAVE_MANAGEMENT', is_active = true
            WHERE page_code = 'LEAVE_REQUESTS'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET offering_code = NULL, is_active = true
            WHERE page_code IN (
                'TENANT_OVERVIEW',
                'TENANT_USERS',
                'TENANT_ROLES',
                'TENANT_CONFIGURATIONS'
            )
            """
        )
    )


def downgrade() -> None:
    # Reactivating unknown legacy pages is unsafe; only restore offering codes.
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET offering_code = 'TASK_MANAGEMENT'
            WHERE app_scope = 'tenant' AND module = 'task_management'
            """
        )
    )
