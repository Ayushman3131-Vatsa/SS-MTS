"""update platform default roles scopes

Revision ID: 0047
Revises: 0046
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0047"
down_revision: Union[str, None] = "0046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE platform_default_roles
            SET module_scope = 'tenant_administration'
            WHERE offering_id IS NULL
              AND role_code IN ('SEC_ADMIN', 'TEN_SEC')
              AND module_scope IN ('CORE', 'core', '')
            """
        )
    )


def downgrade() -> None:
    pass
