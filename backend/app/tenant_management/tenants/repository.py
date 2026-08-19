import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tenant_management.models.enums import SubscriptionPlanCode, TenantOfferingStatus
from app.tenant_management.models.offering import Offering
from app.tenant_management.models.platform_activity_event import PlatformActivityEvent
from app.tenant_management.models.subscription_plan import SubscriptionPlan
from app.tenant_management.models.tenant import Tenant
from app.tenant_management.models.tenant_database_allocation import TenantDatabaseAllocation
from app.tenant_management.models.tenant_subscription import TenantSubscription
from app.tenant_management.models.tenant_offering import TenantOffering, TenantOfferingEvent
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
    entitlement_id: uuid.UUID | None = None
    status: str = TenantOfferingStatus.ACTIVE.value
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    suspended_at: datetime | None = None
    deactivated_at: datetime | None = None
    reason: str | None = None
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None


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
    alternate_contact_name: str | None
    alternate_contact_email: str | None
    alternate_contact_phone: str | None
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
    version: int


@dataclass(frozen=True)
class TenantPage:
    items: tuple[TenantReadModel, ...]
    total: int
    page: int
    page_size: int


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
            Tenant.alternate_contact_name,
            Tenant.alternate_contact_email,
            Tenant.alternate_contact_phone,
            Tenant.subscription_plan,
            SubscriptionPlan.code.label("subscription_plan_code"),
            TenantSubscription.ends_at.label("subscription_ends_at"),
            Tenant.status,
            TenantDatabaseAllocation.mode.label("database_mode"),
            TenantDatabaseAllocation.provisioning_state.label("database_provisioning_state"),
            user_count.label("user_count"),
            Tenant.created_by_admin_id,
            Tenant.created_at,
            Tenant.updated_at,
            Tenant.version,
        )
        .join(
            TenantSubscription,
            and_(
                TenantSubscription.tenant_id == Tenant.tenant_id,
                TenantSubscription.is_current.is_(True),
            ),
        )
        .join(SubscriptionPlan, SubscriptionPlan.plan_id == TenantSubscription.plan_id)
        .join(TenantDatabaseAllocation, TenantDatabaseAllocation.tenant_id == Tenant.tenant_id)
    )


async def get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    return await db.get(Tenant, tenant_id)


async def get_tenant_for_update(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id).with_for_update())
    return result.scalar_one_or_none()


async def get_tenant_by_workspace_slug(db: AsyncSession, workspace_slug: str) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.workspace_slug == workspace_slug))
    return result.scalar_one_or_none()


async def get_tenant_by_code(db: AsyncSession, tenant_code: str) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.tenant_code == tenant_code))
    return result.scalar_one_or_none()


async def get_subscription_plan(db: AsyncSession, code: SubscriptionPlanCode) -> SubscriptionPlan | None:
    result = await db.execute(select(SubscriptionPlan).where(SubscriptionPlan.code == code.value))
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
        select(Offering).where(Offering.status == "ACTIVE").order_by(Offering.sort_order, Offering.display_name)
    )
    return list(result.scalars().all())


async def list_all_offerings(db: AsyncSession) -> list[Offering]:
    result = await db.execute(select(Offering).order_by(Offering.status.desc(), Offering.sort_order, Offering.display_name))
    return list(result.scalars().all())


async def get_active_offerings_by_ids(db: AsyncSession, offering_ids: set[uuid.UUID]) -> list[Offering]:
    if not offering_ids:
        return []
    result = await db.execute(
        select(Offering).where(Offering.offering_id.in_(offering_ids), Offering.status == "ACTIVE")
    )
    return list(result.scalars().all())


def _offering_projection():
    return (
        Offering.offering_id,
        Offering.code,
        Offering.display_name,
        Offering.description,
        Offering.icon_key,
        Offering.route_slug,
        Offering.sort_order,
        TenantOffering.entitlement_id,
        case(
            (
                and_(
                    TenantOffering.status.in_(
                        (
                            TenantOfferingStatus.ACTIVE.value,
                            TenantOfferingStatus.SUSPENDED.value,
                        )
                    ),
                    TenantOffering.ends_at.is_not(None),
                    TenantOffering.ends_at <= func.now(),
                ),
                TenantOfferingStatus.EXPIRED.value,
            ),
            else_=TenantOffering.status,
        ).label("status"),
        TenantOffering.starts_at,
        TenantOffering.ends_at,
        TenantOffering.suspended_at,
        TenantOffering.deactivated_at,
        TenantOffering.reason,
        TenantOffering.version,
        TenantOffering.created_at,
        TenantOffering.updated_at,
    )


async def list_tenant_offerings(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    effective_only: bool = True,
) -> list[OfferingReadModel]:
    conditions = [TenantOffering.tenant_id == tenant_id]
    if effective_only:
        conditions.extend(
            [
                TenantOffering.status == TenantOfferingStatus.ACTIVE.value,
                TenantOffering.starts_at <= func.now(),
                or_(TenantOffering.ends_at.is_(None), TenantOffering.ends_at > func.now()),
            ]
        )
    result = await db.execute(
        select(*_offering_projection())
        .join(Offering, Offering.offering_id == TenantOffering.offering_id)
        .where(*conditions)
        .order_by(Offering.sort_order, Offering.display_name, TenantOffering.created_at.desc())
    )
    return [OfferingReadModel(**row) for row in result.mappings().all()]


async def get_entitlement(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    entitlement_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> TenantOffering | None:
    statement = select(TenantOffering).where(
        TenantOffering.tenant_id == tenant_id,
        TenantOffering.entitlement_id == entitlement_id,
    )
    if for_update:
        statement = statement.with_for_update()
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def get_entitlement_read_model(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    entitlement_id: uuid.UUID,
) -> OfferingReadModel | None:
    result = await db.execute(
        select(*_offering_projection())
        .join(Offering, Offering.offering_id == TenantOffering.offering_id)
        .where(
            TenantOffering.tenant_id == tenant_id,
            TenantOffering.entitlement_id == entitlement_id,
        )
    )
    row = result.mappings().one_or_none()
    return OfferingReadModel(**row) if row is not None else None


async def get_open_entitlement(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    offering_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> TenantOffering | None:
    statement = select(TenantOffering).where(
        TenantOffering.tenant_id == tenant_id,
        TenantOffering.offering_id == offering_id,
        TenantOffering.status.in_((TenantOfferingStatus.ACTIVE.value, TenantOfferingStatus.SUSPENDED.value)),
    )
    if for_update:
        statement = statement.with_for_update()
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def get_event_by_idempotency_key(db: AsyncSession, key: str) -> TenantOfferingEvent | None:
    result = await db.execute(select(TenantOfferingEvent).where(TenantOfferingEvent.idempotency_key == key))
    return result.scalar_one_or_none()


async def list_tenant_offering_events(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[TenantOfferingEvent]:
    result = await db.execute(
        select(TenantOfferingEvent)
        .where(TenantOfferingEvent.tenant_id == tenant_id)
        .order_by(TenantOfferingEvent.occurred_at.desc(), TenantOfferingEvent.event_id.desc())
    )
    return list(result.scalars().all())


async def get_platform_activity_by_idempotency_key(
    db: AsyncSession, key: str
) -> PlatformActivityEvent | None:
    result = await db.execute(
        select(PlatformActivityEvent).where(
            PlatformActivityEvent.idempotency_key == key
        )
    )
    return result.scalar_one_or_none()


async def tenant_has_effective_offering(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    offering_code: str,
) -> bool:
    result = await db.execute(
        select(func.count())
        .select_from(TenantOffering)
        .join(Offering, Offering.offering_id == TenantOffering.offering_id)
        .where(
            TenantOffering.tenant_id == tenant_id,
            Offering.code == offering_code,
            TenantOffering.status == TenantOfferingStatus.ACTIVE.value,
            TenantOffering.starts_at <= func.now(),
            or_(TenantOffering.ends_at.is_(None), TenantOffering.ends_at > func.now()),
        )
    )
    return bool(result.scalar_one())


async def get_offering_access_denial_code(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    offering_code: str,
) -> str | None:
    """Return a stable authorization error code, or None when access is valid."""
    rows = await db.execute(
        select(
            TenantOffering.status,
            TenantOffering.starts_at,
            TenantOffering.ends_at,
            TenantOffering.created_at,
            (
                TenantOffering.ends_at.is_not(None)
                & (TenantOffering.ends_at <= func.now())
            ).label("is_expired"),
        )
        .join(Offering, Offering.offering_id == TenantOffering.offering_id)
        .where(
            TenantOffering.tenant_id == tenant_id,
            Offering.code == offering_code,
        )
        .order_by(
            case(
                (
                    TenantOffering.status.in_(
                        (
                            TenantOfferingStatus.ACTIVE.value,
                            TenantOfferingStatus.SUSPENDED.value,
                        )
                    ),
                    0,
                ),
                else_=1,
            ),
            TenantOffering.created_at.desc(),
        )
    )
    entitlement_rows = rows.all()
    if not entitlement_rows:
        return "OFFERING_NOT_ENTITLED"

    now = await db.scalar(select(func.now()))
    if now is None:
        raise RuntimeError("Database did not return its current timestamp")
    for row in entitlement_rows:
        if row.status == TenantOfferingStatus.EXPIRED.value:
            return "OFFERING_EXPIRED"
        if row.is_expired:
            return "OFFERING_EXPIRED"
        if row.status == TenantOfferingStatus.SUSPENDED.value:
            return "OFFERING_SUSPENDED"
        if row.status == TenantOfferingStatus.DEACTIVATED.value:
            return "OFFERING_DEACTIVATED"
        if row.status == TenantOfferingStatus.ACTIVE.value:
            if row.starts_at > now:
                return "OFFERING_NOT_STARTED"
            return None
    return "OFFERING_NOT_EFFECTIVE"


async def get_tenant_details(db: AsyncSession, tenant_id: uuid.UUID) -> TenantReadModel | None:
    result = await db.execute(_tenant_details_statement().where(Tenant.tenant_id == tenant_id))
    row = result.mappings().one_or_none()
    if row is None:
        return None
    offerings = await list_tenant_offerings(db, tenant_id, effective_only=False)
    return TenantReadModel(**row, offerings=tuple(offerings))


async def list_tenants(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 25,
    query: str | None = None,
    status: str | None = None,
) -> TenantPage:
    base = _tenant_details_statement()
    filters = []
    if query:
        pattern = f"%{query.strip()}%"
        filters.append(
            or_(Tenant.org_name.ilike(pattern), Tenant.tenant_code.ilike(pattern), Tenant.workspace_slug.ilike(pattern))
        )
    if status:
        filters.append(Tenant.status == status)
    count_result = await db.execute(select(func.count()).select_from(base.where(*filters).subquery()))
    total = int(count_result.scalar_one())
    result = await db.execute(
        base.where(*filters)
        .order_by(Tenant.created_at.desc(), Tenant.tenant_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.mappings().all()
    items = []
    for row in rows:
        offerings = await list_tenant_offerings(db, row["tenant_id"], effective_only=False)
        items.append(TenantReadModel(**row, offerings=tuple(offerings)))
    return TenantPage(items=tuple(items), total=total, page=page, page_size=page_size)
