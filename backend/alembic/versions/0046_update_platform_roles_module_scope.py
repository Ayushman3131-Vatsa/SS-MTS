"""update platform roles module scope

Revision ID: 0046
Revises: 0045
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0046"
down_revision: Union[str, None] = "0045"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE platform_roles
            SET module_scope = 'platform_administration'
            WHERE module_scope IS NULL
               OR module_scope IN ('platform', 'PLATFORM', 'CORE', 'core', '')
            """
        )
    )


def downgrade() -> None:
    pass
