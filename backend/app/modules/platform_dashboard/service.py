from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.platform_dashboard import repository
from app.schemas.platform_dashboard import (
    ActivityTenant,
    DashboardCharts,
    DashboardFilters,
    DashboardKpis,
    NewRegistrationPoint,
    PlatformDashboardResponse,
    ReadinessChecks,
    ReadinessResponse,
    RecentActivity,
    SubscriptionDistributionPoint,
    TenantGrowthPoint,
)

READINESS_DATABASE_TIMEOUT_SECONDS = 2.0
logger = logging.getLogger(__name__)


async def get_platform_dashboard(
    db: AsyncSession,
    *,
    growth_months: int,
    registration_days: int,
    activity_limit: int,
) -> PlatformDashboardResponse:
    """Load every dashboard section from one repeatable, read-only snapshot."""

    async with db.begin():
        # This session is dedicated to dashboard reads, so this is the first
        # statement in its transaction. PostgreSQL then guarantees every query
        # below observes the same committed snapshot.
        await db.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        )
        kpis = await repository.get_kpis(db)
        tenant_growth = await repository.get_tenant_growth(
            db,
            growth_months=growth_months,
        )
        new_registrations = await repository.get_new_registrations(
            db,
            registration_days=registration_days,
        )
        subscription_distribution = (
            await repository.get_subscription_distribution(db)
        )
        activity_rows = await repository.get_recent_activity(
            db,
            activity_limit=activity_limit,
        )

    recent_activity = [
        RecentActivity(
            activity_id=row["activity_id"],
            event_type=row["event_type"],
            occurred_at=row["occurred_at"],
            tenant=ActivityTenant(
                tenant_id=row["tenant_id"],
                tenant_name=row["tenant_name"],
            ),
            metadata=row["metadata"] or {},
        )
        for row in activity_rows
    ]

    return PlatformDashboardResponse(
        generated_at=kpis.pop("generated_at"),
        filters=DashboardFilters(
            growth_months=growth_months,
            registration_days=registration_days,
        ),
        kpis=DashboardKpis.model_validate(kpis),
        charts=DashboardCharts(
            tenant_growth=[
                TenantGrowthPoint.model_validate(row) for row in tenant_growth
            ],
            new_registrations=[
                NewRegistrationPoint.model_validate(row)
                for row in new_registrations
            ],
            subscription_distribution=[
                SubscriptionDistributionPoint.model_validate(row)
                for row in subscription_distribution
            ],
        ),
        recent_activity=recent_activity,
    )


async def get_readiness(db: AsyncSession) -> ReadinessResponse:
    database_status = "healthy"
    try:
        await asyncio.wait_for(
            db.execute(text("SELECT 1")),
            timeout=READINESS_DATABASE_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        # A readiness response is deliberately diagnostic-light. Operators
        # should use server logs/telemetry for the underlying database error.
        logger.warning(
            "Primary database readiness check failed (%s)",
            type(exc).__name__,
            exc_info=exc,
        )
        database_status = "unavailable"

    status = "healthy" if database_status == "healthy" else "degraded"
    return ReadinessResponse(
        status=status,
        checked_at=datetime.now(UTC),
        checks=ReadinessChecks(
            api="healthy",
            database=database_status,
        ),
    )
