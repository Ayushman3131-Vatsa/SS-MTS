"""Add alternate tenant contact fields.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE tenants
            ADD COLUMN IF NOT EXISTS alternate_contact_name VARCHAR(255),
            ADD COLUMN IF NOT EXISTS alternate_contact_email CITEXT,
            ADD COLUMN IF NOT EXISTS alternate_contact_phone VARCHAR(40)
        """
    )


def downgrade() -> None:
    op.drop_column("tenants", "alternate_contact_phone")
    op.drop_column("tenants", "alternate_contact_email")
    op.drop_column("tenants", "alternate_contact_name")
