import uuid

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.auth.deps import Principal
from app.common.exceptions import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.common.security import (
    hash_password,
    normalize_email,
    normalize_workspace_slug,
    validate_password,
)
from app.tenant_management.models.enums import (
    DatabaseIsolationMode,
    DatabaseProvisioningState,
    PlatformActivityType,
    PlatformActorType,
    SubscriptionPlanStatus,
    TenantStatus,
    TenantSubscriptionStatus,
)
from app.auth.roles import assign_role, seed_tenant_system_roles
from app.tenant_management.models.platform_activity_event import PlatformActivityEvent
from app.tenant_management.models.tenant import Tenant
from app.tenant_management.models.tenant_database_allocation import TenantDatabaseAllocation
from app.tenant_management.models.tenant_offering import TenantOffering
from app.tenant_management.models.tenant_subscription import TenantSubscription
from app.auth.models.user_account import UserAccount
from app.tenant_management.tenants import repository
from app.tenant_management.schemas.tenant import (
    OfferingResponse,
    RegistrationDefaultsResponse,
    SubscriptionPlanOptionResponse,
    TenantCreateRequest,
    TenantRegistrationOptionsResponse,
)


async def _resolve_workspace_slug(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    org_name: str,
    requested_slug: str | None,
) -> str:
    base_slug = normalize_workspace_slug(requested_slug or org_name)
    # Serialize allocations for the same base slug so two onboarding requests
    # cannot both observe it as available before the unique constraint runs.
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:workspace_slug, 0))"),
        {"workspace_slug": base_slug},
    )
    existing = await repository.get_tenant_by_workspace_slug(db, base_slug)
    if existing is None:
        return base_slug
    if requested_slug is not None:
        raise ConflictError("This workspace slug is already in use")

    for suffix_length in range(8, 33, 4):
        suffix = tenant_id.hex[:suffix_length]
        candidate = f"{base_slug[: 62 - suffix_length]}-{suffix}"
        if await repository.get_tenant_by_workspace_slug(db, candidate) is None:
            return candidate
    raise ConflictError("Unable to allocate a unique workspace slug")


async def _resolve_tenant_code(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    workspace_slug: str,
    requested_code: str | None,
) -> str:
    base_code = requested_code or workspace_slug.replace("-", "_").upper()
    base_code = base_code[:30]
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:tenant_code, 1))"),
        {"tenant_code": base_code},
    )
    if await repository.get_tenant_by_code(db, base_code) is None:
        return base_code
    if requested_code is not None:
        raise ConflictError("This tenant code is already in use")

    for suffix_length in range(6, 13, 2):
        suffix = tenant_id.hex[:suffix_length].upper()
        candidate = f"{base_code[: 29 - suffix_length]}_{suffix}"
        if await repository.get_tenant_by_code(db, candidate) is None:
            return candidate
    raise ConflictError("Unable to allocate a unique tenant code")


async def create_tenant(
    db: AsyncSession,
    principal: Principal,
    payload: TenantCreateRequest,
) -> repository.TenantReadModel:
    """Only a platform_admins row can insert into tenants. In the same
    transaction, seeds the first users row with role='Tenant Admin' and
    created_by_user_id=NULL, per the onboarding rule in the architecture doc."""
    if principal.type != "admin" or principal.tenant_id is not None:
        raise ForbiddenError("Only a Platform Admin can create a tenant")

    plan_code = payload.resolved_subscription_plan_code
    plan = await repository.get_subscription_plan(db, plan_code)
    if plan is None or plan.status != SubscriptionPlanStatus.ACTIVE.value:
        raise BusinessRuleError("The selected subscription plan is not available")

    database_now = await db.scalar(select(func.now()))
    if database_now is None:
        raise RuntimeError("Database did not return its current timestamp")
    if (
        payload.subscription_ends_at is not None
        and payload.subscription_ends_at <= database_now
    ):
        raise BusinessRuleError("subscription_ends_at must be in the future")

    tenant_id = uuid.uuid4()
    workspace_slug = await _resolve_workspace_slug(
        db,
        tenant_id=tenant_id,
        org_name=payload.org_name,
        requested_slug=payload.workspace_slug,
    )
    tenant_code = await _resolve_tenant_code(
        db,
        tenant_id=tenant_id,
        workspace_slug=workspace_slug,
        requested_code=payload.tenant_code,
    )
    offering_ids = set(payload.offering_ids)
    offerings = await repository.get_active_offerings_by_ids(db, offering_ids)
    if len(offerings) != len(offering_ids):
        raise BusinessRuleError("One or more selected offerings are not available")
    admin_email = normalize_email(str(payload.tenant_admin_email))
    validate_password(
        payload.tenant_admin_password,
        email=admin_email,
        name=payload.tenant_admin_name,
        org_name=payload.org_name,
        workspace_slug=workspace_slug,
    )

    tenant = Tenant(
        tenant_id=tenant_id,
        org_name=payload.org_name,
        tenant_code=tenant_code,
        workspace_slug=workspace_slug,
        legal_name=payload.legal_name,
        industry=payload.industry,
        company_size=payload.company_size,
        website=payload.website,
        registration_number=payload.registration_number,
        tax_identifier=payload.tax_identifier,
        address_line_1=payload.address_line_1,
        address_line_2=payload.address_line_2,
        city=payload.city,
        state_province=payload.state_province,
        country=payload.country,
        postal_code=payload.postal_code,
        contact_name=payload.contact_name,
        contact_email=(
            normalize_email(str(payload.contact_email))
            if payload.contact_email is not None
            else None
        ),
        contact_phone=payload.contact_phone,
        subscription_plan=plan.display_name,
        status=payload.status.value,
        created_by_admin_id=principal.id,
    )
    db.add(tenant)
    await db.flush()

    subscription = TenantSubscription(
        tenant_id=tenant.tenant_id,
        plan_id=plan.plan_id,
        starts_at=database_now,
        ends_at=payload.subscription_ends_at,
        is_current=True,
        status=TenantSubscriptionStatus.ACTIVE.value,
    )
    allocation = TenantDatabaseAllocation(
        tenant_id=tenant.tenant_id,
        mode=payload.database_mode.value,
        provisioning_state=DatabaseProvisioningState.READY.value,
        ready_at=database_now,
    )
    db.add_all((subscription, allocation))
    db.add_all(
        TenantOffering(
            tenant_id=tenant.tenant_id,
            offering_id=offering.offering_id,
            licensed_by_admin_id=principal.id,
            licensed_at=database_now,
        )
        for offering in offerings
    )

    roles = await seed_tenant_system_roles(db, tenant.tenant_id)
    tenant_admin_role = roles["TENANT_ADMIN"]

    tenant_admin = UserAccount(
        tenant_id=tenant.tenant_id,
        display_name=payload.tenant_admin_name,
        email=admin_email,
        password_hash=hash_password(payload.tenant_admin_password),
        created_by_user_id=None,
        is_active=True,
    )
    db.add(tenant_admin)
    await db.flush()
    await assign_role(db, user_id=tenant_admin.id, role=tenant_admin_role, assigned_by=None)

    db.add(
        PlatformActivityEvent(
            event_type=PlatformActivityType.TENANT_CREATED.value,
            tenant_id=tenant.tenant_id,
            tenant_name_snapshot=tenant.org_name,
            actor_id=principal.id,
            actor_type=PlatformActorType.PLATFORM_ADMIN.value,
            occurred_at=database_now,
            event_metadata={
                "workspace_slug": tenant.workspace_slug,
                "tenant_code": tenant.tenant_code,
                "subscription_plan_code": plan.code,
                "offering_codes": sorted(offering.code for offering in offerings),
            },
            idempotency_key=f"tenant-created:{tenant.tenant_id}",
        )
    )

    # changed_by_user_id is left NULL for both entries: the actor is a
    # platform admin, not a tenant user, and tenants.created_by_admin_id
    # already records which admin performed the onboarding.
    await record_audit(
        db,
        tenant_id=tenant.tenant_id,
        entity_type="tenant",
        entity_id=tenant.tenant_id,
        action="CREATE",
        changed_by_user_id=None,
        new_value={
            "org_name": tenant.org_name,
            "workspace_slug": tenant.workspace_slug,
            "tenant_code": tenant.tenant_code,
            "subscription_plan": tenant.subscription_plan,
            "subscription_plan_code": plan.code,
            "status": tenant.status,
            "database_mode": allocation.mode,
            "offering_codes": sorted(offering.code for offering in offerings),
        },
    )
    await record_audit(
        db,
        tenant_id=tenant.tenant_id,
        entity_type="user",
        entity_id=tenant_admin.id,
        action="CREATE",
        changed_by_user_id=None,
        new_value={
            "name": tenant_admin.display_name,
            "email": tenant_admin.email,
            "role": "Tenant Admin",
        },
    )

    await db.commit()
    created = await repository.get_tenant_details(db, tenant.tenant_id)
    if created is None:
        raise RuntimeError("Created tenant persistence graph could not be reloaded")
    return created


async def get_tenant_or_404(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> repository.TenantReadModel:
    tenant = await repository.get_tenant_details(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")
    return tenant


async def list_tenants(db: AsyncSession) -> list[repository.TenantReadModel]:
    return await repository.list_tenants(db)


async def get_registration_options(
    db: AsyncSession,
) -> TenantRegistrationOptionsResponse:
    plans = await repository.list_active_subscription_plans(db)
    offerings = await repository.list_active_offerings(db)
    return TenantRegistrationOptionsResponse(
        plans=[
            SubscriptionPlanOptionResponse(
                code=plan.code,
                display_name=plan.display_name,
                price=plan.price,
                currency=plan.currency,
                billing_interval=plan.billing_interval,
                max_users=plan.max_users,
                requires_end_date=plan.code != "FREE",
            )
            for plan in plans
        ],
        offerings=[OfferingResponse.model_validate(offering) for offering in offerings],
        statuses=list(TenantStatus),
        database_modes=list(DatabaseIsolationMode),
        defaults=RegistrationDefaultsResponse(
            subscription_plan_code="FREE",
            status=TenantStatus.ACTIVE,
            database_mode=DatabaseIsolationMode.SHARED,
        ),
    )
