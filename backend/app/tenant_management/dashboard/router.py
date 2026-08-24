from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import Principal, require_platform_admin
from app.common.db.session import db_manager, get_db
from app.tenant_management.dashboard import service
from app.tenant_management.schemas.platform_dashboard import (
    GrowthMonths,
    PlatformDashboardResponse,
    ReadinessResponse,
    RegistrationDays,
)

router = APIRouter(tags=["platform"])


async def get_dashboard_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a session that is independent from the auth dependency.

    Reporting tables are not FORCE RLS. This session must not run SET LOCAL
    GUC statements before SET TRANSACTION ISOLATION LEVEL.
    """

    async with db_manager.session_for() as db:
        yield db


@router.get(
    "/platform/dashboard",
    response_model=PlatformDashboardResponse,
    summary="Get the Platform Admin dashboard",
)
async def get_platform_dashboard(
    response: Response,
    growth_months: Annotated[GrowthMonths, Query()] = 12,
    registration_days: Annotated[RegistrationDays, Query()] = 30,
    activity_limit: Annotated[int, Query(ge=1, le=25)] = 10,
    _principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_dashboard_db),
) -> PlatformDashboardResponse:
    response.headers["Cache-Control"] = "private, no-store"
    return await service.get_platform_dashboard(
        db,
        growth_months=growth_months,
        registration_days=registration_days,
        activity_limit=activity_limit,
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    tags=["health"],
    summary="Check API and primary database readiness",
)
async def readiness(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> ReadinessResponse:
    readiness_result = await service.get_readiness(db)
    response.headers["Cache-Control"] = "no-store"
    if readiness_result.status == "degraded":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return readiness_result
