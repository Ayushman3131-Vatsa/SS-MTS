"""align activity types and login employee_id

Revision ID: 0034
Revises: 0033
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACTIVITY_TYPES = (
    "'TENANT_CREATED', 'PLAN_CHANGED', 'TENANT_SUSPENDED', "
    "'TENANT_REACTIVATED', 'DATABASE_ALLOCATION_READY', "
    "'DATABASE_ALLOCATION_FAILED', 'TENANT_ACTIVATED', "
    "'OFFERING_GRANTED', 'OFFERING_SUSPENDED', 'OFFERING_RESUMED', "
    "'OFFERING_DEACTIVATED', 'OFFERING_EXPIRED', "
    "'OFFERING_CATALOG_CREATED', 'OFFERING_CATALOG_UPDATED', "
    "'OFFERING_CATALOG_ACTIVATED', 'OFFERING_CATALOG_DEACTIVATED', "
    "'OFFERING_CATALOG_DELETED', "
    "'DEFAULT_TEMPLATE_CREATED', 'DEFAULT_TEMPLATE_UPDATED', "
    # Keep intermediate upgrades valid when application code has already
    # written events introduced by later revisions.
    "'DEFAULT_ROLE_CREATED', 'DEFAULT_ROLE_UPDATED', 'DEFAULT_ROLE_DELETED', "
    "'TENANT_ADMIN_ENABLED', 'TENANT_ADMIN_PASSWORD_REGENERATED'"
)


def upgrade() -> None:
    op.execute("ALTER TABLE platform_activity_events DROP CONSTRAINT IF EXISTS check_platform_activity_events_type")
    op.create_check_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        f"event_type IN ({_ACTIVITY_TYPES})",
    )

    connection = op.get_bind()
    column_type = connection.execute(
        sa.text(
            """
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'user_accounts'
              AND column_name = 'employee_id'
            """
        )
    ).scalar()
    if column_type is None:
        op.add_column("user_accounts", sa.Column("employee_id", sa.String(length=50), nullable=True))
        return
    if column_type == "uuid":
        op.execute("ALTER TABLE user_accounts DROP CONSTRAINT IF EXISTS fk_user_accounts_employee_id")
        op.execute(
            """
            ALTER TABLE user_accounts
            ALTER COLUMN employee_id TYPE VARCHAR(50)
            USING CASE WHEN employee_id IS NULL THEN NULL ELSE employee_id::text END
            """
        )


def downgrade() -> None:
    op.execute("ALTER TABLE platform_activity_events DROP CONSTRAINT IF EXISTS check_platform_activity_events_type")
    op.create_check_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        "event_type IN ("
        "'TENANT_CREATED', 'PLAN_CHANGED', 'TENANT_SUSPENDED', "
        "'TENANT_REACTIVATED', 'DATABASE_ALLOCATION_READY', "
        "'DATABASE_ALLOCATION_FAILED')",
    )
