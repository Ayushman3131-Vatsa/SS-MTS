"""add offering catalog activity types

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-06
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_BASE_TYPES = (
    "'TENANT_CREATED', 'PLAN_CHANGED', 'TENANT_SUSPENDED', "
    "'TENANT_REACTIVATED', 'DATABASE_ALLOCATION_READY', "
    "'DATABASE_ALLOCATION_FAILED', 'TENANT_ACTIVATED', "
    "'OFFERING_GRANTED', 'OFFERING_SUSPENDED', 'OFFERING_RESUMED', "
    "'OFFERING_DEACTIVATED', 'OFFERING_EXPIRED'"
)
_CATALOG_TYPES = (
    "'OFFERING_CATALOG_CREATED', 'OFFERING_CATALOG_UPDATED', "
    "'OFFERING_CATALOG_ACTIVATED', 'OFFERING_CATALOG_DEACTIVATED', "
    "'OFFERING_CATALOG_DELETED'"
)


def upgrade() -> None:
    op.drop_constraint("check_platform_activity_events_type", "platform_activity_events", type_="check")
    op.create_check_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        f"event_type IN ({_BASE_TYPES}, {_CATALOG_TYPES})",
    )


def downgrade() -> None:
    op.drop_constraint("check_platform_activity_events_type", "platform_activity_events", type_="check")
    op.create_check_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        f"event_type IN ({_BASE_TYPES})",
    )
