from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_kpis(db: AsyncSession) -> dict[str, Any]:
    """Return all KPI values from one statement-level snapshot."""

    result = await db.execute(
        text(
            """
            SELECT
                CURRENT_TIMESTAMP AS generated_at,
                (SELECT count(*) FROM tenants) AS total_tenants,
                (
                    SELECT count(*)
                    FROM tenants AS tenant
                    WHERE tenant.status = 'ACTIVE'
                      AND EXISTS (
                          SELECT 1
                          FROM tenant_database_allocations AS allocation
                          WHERE allocation.tenant_id = tenant.tenant_id
                            AND allocation.provisioning_state = 'READY'
                      )
                      AND EXISTS (
                          SELECT 1
                          FROM tenant_subscriptions AS subscription
                          WHERE subscription.tenant_id = tenant.tenant_id
                            AND subscription.is_current IS TRUE
                            AND subscription.status = 'ACTIVE'
                            AND (
                                subscription.ends_at IS NULL
                                OR subscription.ends_at >= CURRENT_TIMESTAMP
                            )
                      )
                ) AS active_tenants,
                (
                    SELECT count(*)
                    FROM tenant_database_allocations
                    WHERE mode = 'DEDICATED'
                      AND provisioning_state = 'READY'
                ) AS dedicated_databases,
                (
                    SELECT count(*)
                    FROM tenant_database_allocations
                    WHERE mode = 'SHARED'
                      AND provisioning_state = 'READY'
                ) AS shared_database_tenants,
                (SELECT count(*) FROM users) AS total_users,
                (
                    SELECT count(*)
                    FROM tenants
                    WHERE created_at >= (
                        date_trunc('month', timezone('UTC', CURRENT_TIMESTAMP))
                        AT TIME ZONE 'UTC'
                    )
                      AND created_at < (
                        (
                            date_trunc(
                                'month',
                                timezone('UTC', CURRENT_TIMESTAMP)
                            ) + interval '1 month'
                        ) AT TIME ZONE 'UTC'
                      )
                ) AS new_tenants_this_month,
                (
                    SELECT count(DISTINCT tenant_id)
                    FROM tenant_subscriptions
                    WHERE is_current IS TRUE
                      AND ends_at IS NOT NULL
                      AND ends_at < CURRENT_TIMESTAMP
                ) AS expired_subscriptions
            """
        )
    )
    return dict(result.mappings().one())


async def get_tenant_growth(
    db: AsyncSession,
    *,
    growth_months: int,
) -> list[dict[str, Any]]:
    # The current month counts as one bucket, so a 12-month view starts eleven
    # months before it. Historical tenants are counted once, then the bounded
    # monthly counts are accumulated with a window function. This keeps the
    # work constant as the number of chart buckets grows.
    result = await db.execute(
        text(
            """
            WITH bounds AS (
                SELECT
                    date_trunc(
                        'month',
                        timezone('UTC', CURRENT_TIMESTAMP)
                    ) - make_interval(
                        months => CAST(:month_offset AS integer)
                    ) AS start_month,
                    date_trunc(
                        'month',
                        timezone('UTC', CURRENT_TIMESTAMP)
                    ) AS end_month
            ),
            months AS (
                SELECT generate_series(
                    bounds.start_month,
                    bounds.end_month,
                    interval '1 month'
                )::date AS month
                FROM bounds
            ),
            historical AS (
                SELECT count(*) AS tenant_count
                FROM tenants, bounds
                WHERE tenants.created_at < (
                    bounds.start_month AT TIME ZONE 'UTC'
                )
            ),
            monthly_counts AS (
                SELECT
                    date_trunc(
                        'month',
                        timezone('UTC', tenants.created_at)
                    )::date AS month,
                    count(*) AS tenant_count
                FROM tenants, bounds
                WHERE tenants.created_at >= (
                        bounds.start_month AT TIME ZONE 'UTC'
                    )
                  AND tenants.created_at < (
                        (bounds.end_month + interval '1 month')
                        AT TIME ZONE 'UTC'
                    )
                GROUP BY date_trunc(
                    'month',
                    timezone('UTC', tenants.created_at)
                )::date
            )
            SELECT
                months.month,
                (
                    historical.tenant_count
                    + sum(COALESCE(monthly_counts.tenant_count, 0)) OVER (
                        ORDER BY months.month
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                    )
                )::bigint AS total_tenants
            FROM months
            CROSS JOIN historical
            LEFT JOIN monthly_counts USING (month)
            ORDER BY months.month
            """
        ),
        {"month_offset": growth_months - 1},
    )
    return [dict(row) for row in result.mappings().all()]


async def get_new_registrations(
    db: AsyncSession,
    *,
    registration_days: int,
) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            """
            WITH days AS (
                SELECT generate_series(
                    timezone('UTC', CURRENT_TIMESTAMP)::date
                        - CAST(:day_offset AS integer),
                    timezone('UTC', CURRENT_TIMESTAMP)::date,
                    interval '1 day'
                )::date AS date
            ),
            registrations AS (
                SELECT
                    timezone('UTC', created_at)::date AS date,
                    count(*) AS new_tenants
                FROM tenants
                WHERE created_at >= (
                    (
                        timezone('UTC', CURRENT_TIMESTAMP)::date
                            - CAST(:day_offset AS integer)
                    )::timestamp AT TIME ZONE 'UTC'
                )
                GROUP BY timezone('UTC', created_at)::date
            )
            SELECT
                days.date,
                COALESCE(registrations.new_tenants, 0) AS new_tenants
            FROM days
            LEFT JOIN registrations USING (date)
            ORDER BY days.date
            """
        ),
        {"day_offset": registration_days - 1},
    )
    return [dict(row) for row in result.mappings().all()]


async def get_subscription_distribution(
    db: AsyncSession,
) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            """
            SELECT
                plan.code AS plan_code,
                plan.display_name AS plan_name,
                count(*) AS tenant_count
            FROM tenant_subscriptions AS subscription
            JOIN subscription_plans AS plan
              ON plan.plan_id = subscription.plan_id
            WHERE subscription.is_current IS TRUE
            GROUP BY plan.code, plan.display_name
            ORDER BY tenant_count DESC, plan.code
            """
        )
    )
    return [dict(row) for row in result.mappings().all()]


async def get_recent_activity(
    db: AsyncSession,
    *,
    activity_limit: int,
) -> list[dict[str, Any]]:
    result = await db.execute(
        text(
            """
            SELECT
                activity_id,
                event_type,
                occurred_at,
                tenant_id,
                tenant_name_snapshot AS tenant_name,
                metadata
            FROM platform_activity_events
            ORDER BY occurred_at DESC, activity_id DESC
            LIMIT :activity_limit
            """
        ),
        {"activity_limit": activity_limit},
    )
    return [dict(row) for row in result.mappings().all()]
