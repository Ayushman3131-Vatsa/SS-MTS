"""add optional employee_id on tenant user accounts

Revision ID: 0020
Revises: 0019
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS employee_id VARCHAR(50)")


def downgrade() -> None:
    op.drop_column("user_accounts", "employee_id")
