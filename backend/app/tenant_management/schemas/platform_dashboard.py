import uuid
from datetime import date, datetime
from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from app.models.enums import PlatformActivityType


class GrowthMonths(IntEnum):
    SIX = 6
    TWELVE = 12
    TWENTY_FOUR = 24


class RegistrationDays(IntEnum):
    SEVEN = 7
    THIRTY = 30
    NINETY = 90


PlanCode = Literal["FREE", "BASIC", "PRO", "ENTERPRISE"]
class StrictResponseModel(BaseModel):
    """Response contract that cannot silently grow or drift."""

    model_config = ConfigDict(extra="forbid")


class DashboardFilters(StrictResponseModel):
    growth_months: GrowthMonths
    registration_days: RegistrationDays


class DashboardKpis(StrictResponseModel):
    total_tenants: int = Field(ge=0)
    active_tenants: int = Field(ge=0)
    dedicated_databases: int = Field(ge=0)
    shared_database_tenants: int = Field(ge=0)
    total_users: int = Field(ge=0)
    new_tenants_this_month: int = Field(ge=0)
    expired_subscriptions: int = Field(ge=0)


class TenantGrowthPoint(StrictResponseModel):
    month: date
    total_tenants: int = Field(ge=0)


class NewRegistrationPoint(StrictResponseModel):
    date: date
    new_tenants: int = Field(ge=0)


class SubscriptionDistributionPoint(StrictResponseModel):
    plan_code: PlanCode
    plan_name: str = Field(min_length=1, max_length=100)
    tenant_count: int = Field(ge=0)


class ActivityTenant(StrictResponseModel):
    tenant_id: uuid.UUID | None
    tenant_name: str = Field(min_length=1, max_length=255)


class RecentActivity(StrictResponseModel):
    activity_id: uuid.UUID
    event_type: PlatformActivityType
    occurred_at: datetime
    tenant: ActivityTenant
    metadata: dict[str, JsonValue]


class DashboardCharts(StrictResponseModel):
    tenant_growth: list[TenantGrowthPoint]
    new_registrations: list[NewRegistrationPoint]
    subscription_distribution: list[SubscriptionDistributionPoint]


class PlatformDashboardResponse(StrictResponseModel):
    generated_at: datetime
    filters: DashboardFilters
    kpis: DashboardKpis
    charts: DashboardCharts
    recent_activity: list[RecentActivity]


class ReadinessChecks(StrictResponseModel):
    api: Literal["healthy"]
    database: Literal["healthy", "unavailable"]


class ReadinessResponse(StrictResponseModel):
    status: Literal["healthy", "degraded"]
    checked_at: datetime
    checks: ReadinessChecks
