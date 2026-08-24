"""ensure alternate tenant contact columns exist

Revision ID: 0024
Revises: 0023
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0024"
down_revision: Union[str, None] = "0023"
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
    op.execute(
        """
        ALTER TABLE tenants
            DROP COLUMN IF EXISTS alternate_contact_phone,
            DROP COLUMN IF EXISTS alternate_contact_email,
            DROP COLUMN IF EXISTS alternate_contact_name
        """
    )
