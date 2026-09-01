"""Track first-admin enable and credential-rotation activity.

Revision ID: 0043
Revises: 0042
Create Date: 2026-08-21
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0043"
down_revision: Union[str, None] = "0042"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_EXISTING_EVENTS = (
    "'TENANT_CREATED', 'PLAN_CHANGED', 'TENANT_SUSPENDED', "
    "'TENANT_REACTIVATED', 'DATABASE_ALLOCATION_READY', "
    "'DATABASE_ALLOCATION_FAILED', 'TENANT_ACTIVATED', "
    "'OFFERING_GRANTED', 'OFFERING_SUSPENDED', 'OFFERING_RESUMED', "
    "'OFFERING_DEACTIVATED', 'OFFERING_EXPIRED', "
    "'OFFERING_CATALOG_CREATED', 'OFFERING_CATALOG_UPDATED', "
    "'OFFERING_CATALOG_ACTIVATED', 'OFFERING_CATALOG_DEACTIVATED', "
    "'OFFERING_CATALOG_DELETED', 'DEFAULT_TEMPLATE_CREATED', "
    "'DEFAULT_TEMPLATE_UPDATED', 'DEFAULT_ROLE_CREATED', "
    "'DEFAULT_ROLE_UPDATED', 'DEFAULT_ROLE_DELETED'"
)


def _event_constraint(events: str) -> str:
    return f"event_type IN ({events})"


def upgrade() -> None:
    op.drop_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        type_="check",
    )
    op.create_check_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        _event_constraint(
            _EXISTING_EVENTS
            + ", 'TENANT_ADMIN_ENABLED', 'TENANT_ADMIN_PASSWORD_REGENERATED'"
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        type_="check",
    )
    op.create_check_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        _event_constraint(_EXISTING_EVENTS),
    )
