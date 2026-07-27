"""add dashboard query indexes

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-23
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Growth and registration charts filter/group by created_at without
    # constraining tenant status, so the composite status-leading index from
    # 0005 cannot serve these range scans efficiently.
    op.create_index(
        "ix_tenants_created_at",
        "tenants",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tenants_created_at", table_name="tenants")

