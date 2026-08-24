"""Remove legacy Project Manager and Employee tenant system roles.

Revision ID: 0040_remove_legacy_tenant_system_roles
Revises: 0039_repair_task_management_schema
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    assigned = conn.execute(
        sa.text(
            """
            SELECT r.role_code, COUNT(ur.id) AS user_count
            FROM roles r
            JOIN user_roles ur ON ur.role_id = r.id AND ur.is_active IS TRUE
            WHERE r.is_system IS TRUE
              AND r.role_code IN ('PROJECT_MANAGER', 'EMPLOYEE')
            GROUP BY r.role_code
            """
        )
    ).fetchall()

    blocked = [f"{row.role_code} ({row.user_count} users)" for row in assigned if row.user_count]
    if blocked:
        raise RuntimeError(
            "Cannot remove legacy system roles while users are still assigned: "
            + ", ".join(blocked)
            + ". Reassign those users to custom roles first."
        )

    conn.execute(
        sa.text(
            """
            DELETE FROM role_page_access
            WHERE role_id IN (
                SELECT id FROM roles
                WHERE is_system IS TRUE
                  AND role_code IN ('PROJECT_MANAGER', 'EMPLOYEE')
            )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM user_roles
            WHERE role_id IN (
                SELECT id FROM roles
                WHERE is_system IS TRUE
                  AND role_code IN ('PROJECT_MANAGER', 'EMPLOYEE')
            )
            """
        )
    )
    conn.execute(
        sa.text(
            """
            DELETE FROM roles
            WHERE is_system IS TRUE
              AND role_code IN ('PROJECT_MANAGER', 'EMPLOYEE')
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    tenants = conn.execute(sa.text("SELECT tenant_id FROM tenants")).fetchall()
    for (tenant_id,) in tenants:
        for role_code, role_name in (
            ("PROJECT_MANAGER", "Project Manager"),
            ("EMPLOYEE", "Employee"),
        ):
            conn.execute(
                sa.text(
                    """
                    INSERT INTO roles (
                        id, tenant_id, role_code, role_name, description, is_system, is_active
                    )
                    SELECT uuid_generate_v4(), :tenant_id, :role_code, :role_name,
                           :description, true, true
                    WHERE NOT EXISTS (
                        SELECT 1 FROM roles
                        WHERE tenant_id = :tenant_id AND role_code = :role_code
                    )
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "role_code": role_code,
                    "role_name": role_name,
                    "description": f"System role: {role_name}",
                },
            )
