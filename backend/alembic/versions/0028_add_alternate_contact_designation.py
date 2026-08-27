"""Add alternate tenant contact designation.

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-19
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE tenants
            ADD COLUMN IF NOT EXISTS alternate_contact_designation VARCHAR(100)
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE tenants DROP COLUMN IF EXISTS alternate_contact_designation"
    )
