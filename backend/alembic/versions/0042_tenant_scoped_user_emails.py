"""Per-tenant unique user emails; email may be omitted.

Revision ID: 0042
Revises: 0041
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0042"
down_revision: Union[str, None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE user_accounts DROP CONSTRAINT IF EXISTS uq_user_accounts_email")
    op.alter_column(
        "user_accounts",
        "email",
        existing_type=postgresql.CITEXT(),
        nullable=True,
    )
    op.execute("DROP INDEX IF EXISTS uq_user_accounts_tenant_email")
    op.create_index(
        "uq_user_accounts_tenant_email",
        "user_accounts",
        ["tenant_id", "email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_user_accounts_tenant_email")
    op.execute(
        """
        UPDATE user_accounts
        SET email = lower(username::text) || '@accounts.local'
        WHERE email IS NULL
        """
    )
    op.alter_column(
        "user_accounts",
        "email",
        existing_type=postgresql.CITEXT(),
        nullable=False,
    )
    op.create_unique_constraint("uq_user_accounts_email", "user_accounts", ["email"])
