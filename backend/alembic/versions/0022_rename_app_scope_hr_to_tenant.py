"""rename leftover pages.app_scope hr values to tenant

Revision ID: 0022
Revises: 0021
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE pages SET app_scope = 'tenant' WHERE app_scope = 'hr'")


def downgrade() -> None:
    op.execute(
        """
        UPDATE pages
        SET app_scope = 'hr'
        WHERE app_scope = 'tenant'
        """
    )
