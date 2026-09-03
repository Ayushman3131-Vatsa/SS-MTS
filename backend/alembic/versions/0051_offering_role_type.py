"""Add platform and tenant applicability to offerings.

Revision ID: 0051
Revises: 0050
Create Date: 2026-09-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "offerings",
        sa.Column("role_type", sa.String(length=20), nullable=True),
    )
    op.execute(
        """
        UPDATE offerings
        SET role_type = CASE
            WHEN code IN (
                'PLATFORM_ADMINISTRATION',
                'PLATFORM_USER_ACCESS_MANAGEMENT'
            ) THEN 'PLATFORM'
            ELSE 'TENANT'
        END
        """
    )
    op.alter_column(
        "offerings",
        "role_type",
        existing_type=sa.String(length=20),
        nullable=False,
    )
    op.create_check_constraint(
        "check_offerings_role_type",
        "offerings",
        "role_type IN ('PLATFORM', 'TENANT', 'BOTH')",
    )
    op.create_index(
        "ix_offerings_role_type_status",
        "offerings",
        ["role_type", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_offerings_role_type_status", table_name="offerings")
    op.drop_constraint("check_offerings_role_type", "offerings", type_="check")
    op.drop_column("offerings", "role_type")
