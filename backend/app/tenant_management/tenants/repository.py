import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant_management.models.enums import SubscriptionPlanCode
from app.tenant_management.models.offering import Offering
from app.tenant_management.models.subscription_plan import SubscriptionPlan
from app.tenant_management.models.tenant import Tenant
from app.tenant_management.models.tenant_database_allocation import TenantDatabaseAllocation
from app.tenant_management.models.tenant_subscription import TenantSubscription
from app.tenant_management.models.tenant_offering import TenantOffering
from app.auth.models.user_account import UserAccount


@dataclass(frozen=True)
class OfferingReadModel:
    offering_id: uuid.UUID
    code: str
    display_name: str
    description: str
    icon_key: str
    route_slug: str
    sort_order: int


@dataclass(frozen=True)
class TenantReadModel:
    tenant_id: uuid.UUID
    org_name: str
    tenant_code: str
    workspace_slug: str
    legal_name: str | None
    industry: str | None
    company_size: str | None
    website: str | None
    registration_number: str | None
    tax_identifier: str | None
    address_line_1: str | None
    address_line_2: str | None
    city: str | None
    state_province: str | None
    country: str | None
    postal_code: str | None
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    subscription_plan: str
    subscription_plan_code: str
    subscription_ends_at: datetime | None
    status: str
    database_mode: str
    database_provisioning_state: str
    user_count: int
    offerings: tuple[OfferingReadModel, ...]
    created_by_admin_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


def _tenant_details_statement():
    user_count = (
        select(func.count(UserAccount.id))
        .where(UserAccount.tenant_id == Tenant.tenant_id)
        .correlate(Tenant)
        .scalar_subquery()
    )
    return (
        select(
            Tenant.tenant_id,
            Tenant.org_name,
            Tenant.tenant_code,
            Tenant.workspace_slug,
            Tenant.legal_name,
            Tenant.industry,
            Tenant.company_size,
            Tenant.website,
            Tenant.registration_number,
            Tenant.tax_identifier,
            Tenant.address_line_1,
            Tenant.address_line_2,
            Tenant.city,
            Tenant.state_province,
            Tenant.country,
            Tenant.postal_code,
            Tenant.contact_name,
            Tenant.contact_email,
            Tenant.contact_phone,
            Tenant.subscription_plan,
            SubscriptionPlan.code.label("subscription_plan_code"),
            TenantSubscription.ends_at.label("subscription_ends_at"),
            Tenant.status,
            TenantDatabaseAllocation.mode.label("database_mode"),
            TenantDatabaseAllocation.provisioning_state.label(
                "database_provisioning_state"
            ),
            user_count.label("user_count"),
            Tenant.created_by_admin_id,
            Tenant.created_at,
            Tenant.updated_at,
        )
        .join(
            TenantSubscription,
            and_(
                TenantSubscription.tenant_id == Tenant.tenant_id,
                TenantSubscription.is_current.is_(True),
            ),
        )
        .join(
            SubscriptionPlan,
            SubscriptionPlan.plan_id == TenantSubscription.plan_id,
        )
        .join(
            TenantDatabaseAllocation,
            TenantDatabaseAllocation.tenant_id == Tenant.tenant_id,
        )
    )


async def get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    return await db.get(Tenant, tenant_id)


async def get_tenant_by_workspace_slug(db: AsyncSession, workspace_slug: str) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.workspace_slug == workspace_slug))
    return result.scalar_one_or_none()


async def get_tenant_by_code(db: AsyncSession, tenant_code: str) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.tenant_code == tenant_code))
    return result.scalar_one_or_none()


async def get_subscription_plan(
    db: AsyncSession,
    code: SubscriptionPlanCode,
) -> SubscriptionPlan | None:
    result = await db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.code == code.value)
    )
    return result.scalar_one_or_none()


async def list_active_subscription_plans(db: AsyncSession) -> list[SubscriptionPlan]:
    result = await db.execute(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.status == "ACTIVE")
        .order_by(SubscriptionPlan.price.asc().nulls_last(), SubscriptionPlan.display_name)
    )
    return list(result.scalars().all())


async def list_active_offerings(db: AsyncSession) -> list[Offering]:
    result = await db.execute(
        select(Offering)
        .where(Offering.status == "ACTIVE")
        .order_by(Offering.sort_order, Offering.display_name)
    )
    return list(result.scalars().all())


async def get_active_offerings_by_ids(
    db: AsyncSession,
    offering_ids: set[uuid.UUID],
) -> list[Offering]:
    if not offering_ids:
        return []
    result = await db.execute(
        select(Offering).where(
            Offering.offering_id.in_(offering_ids),
            Offering.status == "ACTIVE",
        )
    )
    return list(result.scalars().all())


async def list_tenant_offerings(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> list[OfferingReadModel]:
    result = await db.execute(
        select(
            Offering.offering_id,
            Offering.code,
            Offering.display_name,
            Offering.description,
            Offering.icon_key,
            Offering.route_slug,
            Offering.sort_order,
        )
        .join(TenantOffering, TenantOffering.offering_id == Offering.offering_id)
        .where(TenantOffering.tenant_id == tenant_id, Offering.status == "ACTIVE")
        .order_by(Offering.sort_order, Offering.display_name)
    )
    return [OfferingReadModel(**row) for row in result.mappings().all()]


async def get_tenant_details(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> TenantReadModel | None:
    result = await db.execute(
        _tenant_details_statement().where(Tenant.tenant_id == tenant_id)
    )
    row = result.mappings().one_or_none()
    if row is None:
        return None
    offerings = await list_tenant_offerings(db, tenant_id)
    return TenantReadModel(**row, offerings=tuple(offerings))


async def list_tenants(db: AsyncSession) -> list[TenantReadModel]:
    result = await db.execute(
        _tenant_details_statement().order_by(Tenant.created_at.desc(), Tenant.tenant_id)
    )
    rows = result.mappings().all()
    if not rows:
        return []

    tenant_ids = [row["tenant_id"] for row in rows]
    offering_result = await db.execute(
        select(
            TenantOffering.tenant_id,
            Offering.offering_id,
            Offering.code,
            Offering.display_name,
            Offering.description,
            Offering.icon_key,
            Offering.route_slug,
            Offering.sort_order,
        )
        .join(Offering, Offering.offering_id == TenantOffering.offering_id)
        .where(
            TenantOffering.tenant_id.in_(tenant_ids),
            Offering.status == "ACTIVE",
        )
        .order_by(TenantOffering.tenant_id, Offering.sort_order, Offering.display_name)
    )
    offerings_by_tenant: dict[uuid.UUID, list[OfferingReadModel]] = {
        tenant_id: [] for tenant_id in tenant_ids
    }
    for offering_row in offering_result.mappings().all():
        tenant_id = offering_row["tenant_id"]
        offering_values = {
            key: value for key, value in offering_row.items() if key != "tenant_id"
        }
        offerings_by_tenant[tenant_id].append(OfferingReadModel(**offering_values))
    return [
        TenantReadModel(
            **row,
            offerings=tuple(offerings_by_tenant[row["tenant_id"]]),
        )
        for row in rows
    ]
