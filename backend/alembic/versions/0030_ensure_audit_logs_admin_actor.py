"""ensure audit_logs.changed_by_admin_id exists

Revision ID: 0030
Revises: 0029
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    has_column = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'audit_logs'
                  AND column_name = 'changed_by_admin_id'
            )
            """
        )
    ).scalar()
    if not has_column:
        op.add_column(
            "audit_logs",
            sa.Column("changed_by_admin_id", postgresql.UUID(as_uuid=True), nullable=True),
        )

    has_fk = connection.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_audit_logs_changed_by_admin_id'
            )
            """
        )
    ).scalar()
    if not has_fk:
        op.create_foreign_key(
            "fk_audit_logs_changed_by_admin_id",
            "audit_logs",
            "platform_admins",
            ["changed_by_admin_id"],
            ["admin_id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE audit_logs
            DROP CONSTRAINT IF EXISTS fk_audit_logs_changed_by_admin_id
        """
    )
    op.execute(
        """
        ALTER TABLE audit_logs
            DROP COLUMN IF EXISTS changed_by_admin_id
        """
    )
