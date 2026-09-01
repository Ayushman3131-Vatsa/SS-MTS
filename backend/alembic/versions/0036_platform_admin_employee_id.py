"""add optional employee_id on platform operators

Revision ID: 0036
Revises: 0035
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "platform_admins",
        sa.Column("employee_id", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("platform_admins", "employee_id")
