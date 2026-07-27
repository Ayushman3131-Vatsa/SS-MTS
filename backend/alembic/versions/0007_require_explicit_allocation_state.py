"""require explicit database allocation state

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # READY requires a matching ready_at timestamp. A server default for only
    # half of that invariant made raw/default inserts invalid, so callers must
    # now choose state and timestamp together.
    op.alter_column(
        "tenant_database_allocations",
        "provisioning_state",
        existing_type=sa.String(length=20),
        existing_nullable=False,
        server_default=None,
    )


def downgrade() -> None:
    op.alter_column(
        "tenant_database_allocations",
        "provisioning_state",
        existing_type=sa.String(length=20),
        existing_nullable=False,
        server_default=sa.text("'READY'"),
    )
