"""link pages to offerings and seed entitled module pages

Revision ID: 0019
Revises: 0018
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MODULE_PAGES = (
    ("CORE_HR_EMPLOYEES", "core_hr", "Employees", "/app/modules/core-hr", "tenant", "CORE_HR"),
    ("PAYROLL_RUNS", "payroll", "Payroll", "/app/modules/payroll", "tenant", "PAYROLL"),
    ("LEAVE_REQUESTS", "leave", "Leave", "/app/modules/leave-management", "tenant", "LEAVE_MANAGEMENT"),
)


def upgrade() -> None:
    op.add_column("pages", sa.Column("offering_code", sa.String(length=50), nullable=True))
    op.create_index("ix_pages_offering_code", "pages", ["offering_code"])

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE pages
            SET offering_code = 'TASK_MANAGEMENT'
            WHERE module = 'task_management'
            """
        )
    )

    for page_code, module, page_name, route, app_scope, offering_code in MODULE_PAGES:
        connection.execute(
            sa.text(
                """
                INSERT INTO pages (
                    id, page_code, module, page_name, route, app_scope, offering_code, is_active
                )
                VALUES (
                    uuid_generate_v4(), :page_code, :module, :page_name, :route,
                    :app_scope, :offering_code, true
                )
                ON CONFLICT (page_code) DO UPDATE SET
                    module = EXCLUDED.module,
                    page_name = EXCLUDED.page_name,
                    route = EXCLUDED.route,
                    app_scope = EXCLUDED.app_scope,
                    offering_code = EXCLUDED.offering_code,
                    is_active = true
                """
            ),
            {
                "page_code": page_code,
                "module": module,
                "page_name": page_name,
                "route": route,
                "app_scope": app_scope,
                "offering_code": offering_code,
            },
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM pages WHERE page_code = ANY(:page_codes)"),
        {"page_codes": [page[0] for page in MODULE_PAGES]},
    )
    op.drop_index("ix_pages_offering_code", table_name="pages")
    op.drop_column("pages", "offering_code")
