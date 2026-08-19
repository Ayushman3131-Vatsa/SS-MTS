"""support platform-managed default templates

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0012"
down_revision: Union[str, None] = "0011"
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
_DEFAULT_TEMPLATE_TYPES = (
    "'DEFAULT_TEMPLATE_CREATED', 'DEFAULT_TEMPLATE_UPDATED'"
)


def upgrade() -> None:
    # The legacy schema allowed data shapes that cannot be represented by the
    # platform catalog's stable lookup rules. Fail before changing constraints
    # so operators get a precise, actionable error instead of a generic unique
    # constraint failure (or a lossy category-type backfill).
    op.execute(
        """
        DO $migration$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM config_templates
                GROUP BY code
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    '0012 preflight failed: config_templates.code contains duplicates';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM config_templates
                GROUP BY category_id
                HAVING COUNT(DISTINCT template_type) > 1
            ) THEN
                RAISE EXCEPTION
                    '0012 preflight failed: a config category contains mixed template types';
            END IF;

            IF EXISTS (
                WITH inferred_category_types AS (
                    SELECT
                        category.category_id,
                        category.offering_id,
                        COALESCE(MIN(template.template_type), 'OTHER') AS template_type
                    FROM config_categories AS category
                    LEFT JOIN config_templates AS template
                        ON template.category_id = category.category_id
                    GROUP BY category.category_id, category.offering_id
                )
                SELECT 1
                FROM inferred_category_types
                GROUP BY offering_id, template_type
                HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    '0012 preflight failed: an offering has multiple categories for one template type';
            END IF;
        END
        $migration$;
        """
    )

    op.add_column(
        "config_categories",
        sa.Column(
            "template_type",
            sa.String(length=50),
            server_default=sa.text("'OTHER'"),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE config_categories AS category
        SET template_type = COALESCE(
            (
                SELECT MIN(template.template_type)
                FROM config_templates AS template
                WHERE template.category_id = category.category_id
            ),
            'OTHER'
        )
        """
    )
    op.alter_column("config_categories", "template_type", nullable=False)
    op.create_check_constraint(
        "check_config_categories_type",
        "config_categories",
        "template_type IN ('EMAIL', 'LETTER', 'NOTIFICATION', 'OTHER')",
    )
    op.create_unique_constraint(
        "uq_config_categories_offering_type",
        "config_categories",
        ["offering_id", "template_type"],
    )

    op.drop_constraint(
        "uq_config_templates_category_code",
        "config_templates",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_config_templates_code",
        "config_templates",
        ["code"],
    )
    op.add_column(
        "config_templates",
        sa.Column(
            "version",
            sa.Integer(),
            server_default=sa.text("1"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "check_config_templates_version",
        "config_templates",
        "version >= 1",
    )

    # Older API clients could create a partial override. Normalize those rows
    # into full content snapshots in this same rollout so a subsequent platform
    # edit cannot leak into a tenant-customized template. No tenant rows are
    # created and no separate backfill job is required.
    op.execute(
        """
        UPDATE tenant_config_overrides AS override
        SET
            subject = COALESCE(override.subject, template.subject),
            body = COALESCE(override.body, template.body)
        FROM config_templates AS template
        WHERE template.template_id = override.template_id
          AND (override.subject IS NULL OR override.body IS NULL)
        """
    )
    op.alter_column("tenant_config_overrides", "body", nullable=False)

    op.drop_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        type_="check",
    )
    op.create_check_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        f"event_type IN ({_BASE_TYPES}, {_CATALOG_TYPES}, {_DEFAULT_TEMPLATE_TYPES})",
    )


def downgrade() -> None:
    # The 0011 activity constraint cannot represent feature-specific events.
    # Removing the feature during rollback therefore also removes only its
    # audit rows before restoring the older constraint.
    op.execute(
        """
        DELETE FROM platform_activity_events
        WHERE event_type IN ('DEFAULT_TEMPLATE_CREATED', 'DEFAULT_TEMPLATE_UPDATED')
        """
    )
    op.drop_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        type_="check",
    )
    op.create_check_constraint(
        "check_platform_activity_events_type",
        "platform_activity_events",
        f"event_type IN ({_BASE_TYPES}, {_CATALOG_TYPES})",
    )

    op.alter_column("tenant_config_overrides", "body", nullable=True)

    op.drop_constraint(
        "check_config_templates_version",
        "config_templates",
        type_="check",
    )
    op.drop_column("config_templates", "version")
    op.drop_constraint(
        "uq_config_templates_code",
        "config_templates",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_config_templates_category_code",
        "config_templates",
        ["category_id", "code"],
    )

    op.drop_constraint(
        "uq_config_categories_offering_type",
        "config_categories",
        type_="unique",
    )
    op.drop_constraint(
        "check_config_categories_type",
        "config_categories",
        type_="check",
    )
    op.drop_column("config_categories", "template_type")
