import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.tenant.defaults import ensure_system_role_page_defaults
from app.auth.deps import Principal
from app.auth.email_identity import reserve_new_tenant_contact
from app.auth.first_admin import create_first_tenant_admin, rotate_pending_tenant_admin_password
from app.auth.roles import seed_tenant_system_roles
from app.common.audit import record_audit
from app.common.config import get_settings
from app.common.exceptions import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.common.security import normalize_email
from app.tenant_management.models.enums import (
    DatabaseIsolationMode,
    DatabaseProvisioningState,
    PlatformActivityType,
    PlatformActorType,
    TenantOfferingStatus,
    SubscriptionPlanStatus,
    TenantStatus,
    TenantSubscriptionStatus,
)
from app.tenant_management.models.platform_activity_event import PlatformActivityEvent
from app.tenant_management.models.tenant import Tenant
from app.tenant_management.models.tenant_database_allocation import TenantDatabaseAllocation
from app.tenant_management.models.offering import Offering
from app.tenant_management.models.tenant_offering import TenantOffering, TenantOfferingEvent
from app.tenant_management.models.tenant_subscription import TenantSubscription
from app.tenant_management.tenants import repository
from app.tenant_management.schemas.tenant import (
    OfferingResponse,
    RegistrationDefaultsResponse,
    SubscriptionPlanOptionResponse,
    TenantCreateRequest,
    TenantRegistrationOptionsResponse,
    TenantOfferingActionRequest,
    TenantOfferingGrantRequest,
    TenantOfferingRemovalRequest,
    TenantStatusActionRequest,
)


@dataclass(frozen=True)
class CreatedTenant:
    tenant: repository.TenantReadModel
    first_admin_email: str
    first_admin_username: str
    temporary_password: str


@dataclass(frozen=True)
class RotatedFirstAccess:
    email: str
    username: str
    temporary_password: str


async def _resolve_tenant_code(
    db: AsyncSession,
    *,
    requested_code: str,
) -> str:
    base_code = requested_code.strip().upper()
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:tenant_code, 1))"),
        {"tenant_code": base_code},
    )
    if await repository.get_tenant_by_code(db, base_code) is None:
        return base_code
    raise ConflictError("This tenant code is already in use")


async def create_tenant(
    db: AsyncSession,
    principal: Principal,
    payload: TenantCreateRequest,
) -> CreatedTenant:
    """Create an active tenant, licensed offerings, and first Tenant Admin."""
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

    tenant_code = await _resolve_tenant_code(
        db,
        requested_code=payload.tenant_code,
    )
    contact_email = await reserve_new_tenant_contact(db, str(payload.contact_email))
    tenant_id = uuid.uuid4()
    grant_by_id = {grant.offering_id: grant for grant in payload.offering_grants}
    offering_ids = set(grant_by_id) or set(payload.offering_ids)
    offerings = await repository.get_active_offerings_by_ids(db, offering_ids)
    if len(offerings) != len(offering_ids):
        raise BusinessRuleError("One or more selected offerings are not available")
    tenant = Tenant(
        tenant_id=tenant_id,
        org_name=payload.org_name,
        tenant_code=tenant_code,
        legal_name=payload.legal_name,
        industry=payload.industry,
        company_size=payload.company_size,
        website=payload.website,
        tax_registration_number=payload.tax_registration_number,
        pan_number=payload.pan_number,
        address_line_1=payload.address_line_1,
        address_line_2=payload.address_line_2,
        city=payload.city,
        state_province=payload.state_province,
        country=payload.country,
        postal_code=payload.postal_code,
        contact_name=payload.contact_name,
        contact_designation=payload.contact_designation,
        contact_email=contact_email,
        contact_phone=payload.contact_phone,
        alternate_contact_name=payload.alternate_contact_name,
        alternate_contact_designation=payload.alternate_contact_designation,
        alternate_contact_email=(
            normalize_email(str(payload.alternate_contact_email))
            if payload.alternate_contact_email is not None
            else None
        ),
        alternate_contact_phone=payload.alternate_contact_phone,
        subscription_plan=plan.display_name,
        status=TenantStatus.ACTIVE.value,
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
    entitlement_rows = []
    for offering in offerings:
        grant = grant_by_id.get(offering.offering_id)
        entitlement = TenantOffering(
            tenant_id=tenant.tenant_id,
            offering_id=offering.offering_id,
            licensed_by_admin_id=principal.id,
            status=TenantOfferingStatus.ACTIVE.value,
            starts_at=grant.starts_at if grant is not None else database_now,
            ends_at=grant.ends_at if grant is not None else None,
        )
        entitlement_rows.append(entitlement)
        db.add(entitlement)
    await db.flush()
    for entitlement in entitlement_rows:
        db.add(
            TenantOfferingEvent(
                entitlement_id=entitlement.entitlement_id,
                tenant_id=tenant.tenant_id,
                event_type=PlatformActivityType.OFFERING_GRANTED.value,
                actor_admin_id=principal.id,
                old_value=None,
                new_value={
                    "status": entitlement.status,
                    "starts_at": entitlement.starts_at.isoformat(),
                    "ends_at": entitlement.ends_at.isoformat() if entitlement.ends_at else None,
                },
                idempotency_key=f"tenant-created-offering:{tenant.tenant_id}:{entitlement.offering_id}",
            )
        )

    roles = await seed_tenant_system_roles(db, tenant.tenant_id)
    await ensure_system_role_page_defaults(db, tenant.tenant_id)
    first_admin_email, first_admin_username, temporary_password = await create_first_tenant_admin(
        db,
        tenant=tenant,
        role=roles["TENANT_ADMIN"],
    )

    db.add(
        PlatformActivityEvent(
            event_type=PlatformActivityType.TENANT_CREATED.value,
            tenant_id=tenant.tenant_id,
            tenant_name_snapshot=tenant.org_name,
            actor_id=principal.id,
            actor_type=PlatformActorType.PLATFORM_ADMIN.value,
            occurred_at=database_now,
            event_metadata={
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
        changed_by_admin_id=principal.id,
        new_value={
            "org_name": tenant.org_name,
            "tenant_code": tenant.tenant_code,
            "subscription_plan": tenant.subscription_plan,
            "subscription_plan_code": plan.code,
            "status": tenant.status,
            "database_mode": allocation.mode,
            "offering_codes": sorted(offering.code for offering in offerings),
        },
    )
    await db.commit()
    created = await repository.get_tenant_details(db, tenant.tenant_id)
    if created is None:
        raise RuntimeError("Created tenant persistence graph could not be reloaded")
    return CreatedTenant(
        tenant=created,
        first_admin_email=first_admin_email,
        first_admin_username=first_admin_username,
        temporary_password=temporary_password,
    )


async def get_tenant_or_404(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> repository.TenantReadModel:
    tenant = await repository.get_tenant_details(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")
    return tenant


async def rotate_first_admin_access(
    db: AsyncSession,
    principal: Principal,
    tenant_id: uuid.UUID,
) -> RotatedFirstAccess:
    if principal.type != "admin" or principal.tenant_id is not None:
        raise ForbiddenError("Platform administrator access required")

    tenant_model = await db.get(Tenant, tenant_id)
    if tenant_model is None:
        raise NotFoundError("Tenant not found")

    email, username, temporary_password = await rotate_pending_tenant_admin_password(
        db,
        tenant=tenant_model,
        changed_by_admin_id=principal.id,
    )
    await db.commit()
    return RotatedFirstAccess(email=email, username=username, temporary_password=temporary_password)


async def list_tenants(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 25,
    query: str | None = None,
    status: str | None = None,
) -> repository.TenantPage:
    return await repository.list_tenants(
        db, page=page, page_size=page_size, query=query, status=status
    )


def _require_platform_admin(principal: Principal) -> None:
    if principal.type != "admin" or principal.tenant_id is not None:
        raise ForbiddenError("Only a Platform Admin can manage tenants", code="PLATFORM_ADMIN_REQUIRED")


def _offering_snapshot(offering: Offering) -> dict[str, object]:
    return {
        "offering_id": str(offering.offering_id),
        "code": offering.code,
        "display_name": offering.display_name,
    }


def _entitlement_snapshot(entitlement: TenantOffering) -> dict[str, object]:
    return {
        "entitlement_id": str(entitlement.entitlement_id),
        "offering_id": str(entitlement.offering_id),
        "status": entitlement.status,
        "starts_at": entitlement.starts_at.isoformat(),
        "ends_at": entitlement.ends_at.isoformat() if entitlement.ends_at else None,
        "reason": entitlement.reason,
        "version": entitlement.version,
    }


async def _database_now(db: AsyncSession) -> datetime:
    value = await db.scalar(select(func.now()))
    if value is None:
        raise RuntimeError("Database did not return its current timestamp")
    return value


async def _write_offering_event(
    db: AsyncSession,
    *,
    entitlement: TenantOffering,
    tenant: Tenant,
    offering: Offering,
    principal: Principal | None,
    event_type: str,
    action: str,
    old_value: dict | None,
    new_value: dict | None,
    idempotency_key: str,
    occurred_at: datetime,
) -> None:
    db.add(
        TenantOfferingEvent(
            entitlement_id=entitlement.entitlement_id,
            tenant_id=tenant.tenant_id,
            event_type=event_type,
            actor_admin_id=principal.id if principal is not None else None,
            occurred_at=occurred_at,
            old_value=old_value,
            new_value=new_value,
            idempotency_key=idempotency_key,
        )
    )
    db.add(
        PlatformActivityEvent(
            event_type=event_type,
            tenant_id=tenant.tenant_id,
            tenant_name_snapshot=tenant.org_name,
            actor_id=principal.id if principal is not None else None,
            actor_type=(
                PlatformActorType.PLATFORM_ADMIN.value
                if principal is not None
                else PlatformActorType.SYSTEM.value
            ),
            occurred_at=occurred_at,
            event_metadata={
                "entitlement_id": str(entitlement.entitlement_id),
                "offering": _offering_snapshot(offering),
                "old": old_value or {},
                "new": new_value or {},
            },
            idempotency_key=f"platform:{idempotency_key}",
        )
    )
    await record_audit(
        db,
        tenant_id=tenant.tenant_id,
        entity_type="tenant_offering_entitlement",
        entity_id=entitlement.entitlement_id,
        action=action,
        changed_by_user_id=None,
        changed_by_admin_id=principal.id if principal is not None else None,
        old_value=old_value,
        new_value=new_value,
    )


async def _entitlement_response(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    entitlement_id: uuid.UUID,
) -> repository.OfferingReadModel:
    result = await repository.get_entitlement_read_model(db, tenant_id, entitlement_id)
    if result is None:
        raise NotFoundError("Offering entitlement not found", code="ENTITLEMENT_NOT_FOUND")
    return result


async def grant_offering(
    db: AsyncSession,
    principal: Principal,
    tenant_id: uuid.UUID,
    payload: TenantOfferingGrantRequest,
    *,
    idempotency_key: str,
) -> repository.OfferingReadModel:
    _require_platform_admin(principal)
    existing_event = await repository.get_event_by_idempotency_key(db, idempotency_key)
    if existing_event is not None:
        if existing_event.tenant_id != tenant_id:
            raise ConflictError(
                "Idempotency-Key was already used for another tenant",
                code="IDEMPOTENCY_KEY_REUSED",
            )
        return await _entitlement_response(db, tenant_id, existing_event.entitlement_id)

    tenant = await repository.get_tenant_for_update(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found", code="TENANT_NOT_FOUND")
    if tenant.version != payload.expected_tenant_version:
        raise ConflictError(
            "Tenant was modified by someone else — refresh and retry",
            code="TENANT_VERSION_CONFLICT",
        )
    offering = await db.get(Offering, payload.offering_id)
    if offering is None:
        raise NotFoundError("Offering not found", code="OFFERING_NOT_FOUND")
    if offering.status != "ACTIVE":
        raise BusinessRuleError(
            "Inactive catalog offerings cannot be granted",
            code="OFFERING_CATALOG_INACTIVE",
        )
    now = await _database_now(db)
    if payload.ends_at <= now:
        raise BusinessRuleError(
            "Offering end date must be in the future",
            code="OFFERING_END_IN_PAST",
        )
    if await repository.get_open_entitlement(db, tenant_id, payload.offering_id, for_update=True):
        raise ConflictError(
            "This offering already has an open entitlement for the tenant",
            code="ENTITLEMENT_ALREADY_OPEN",
        )
    entitlement = TenantOffering(
        tenant_id=tenant_id,
        offering_id=payload.offering_id,
        licensed_by_admin_id=principal.id,
        status=TenantOfferingStatus.ACTIVE.value,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        reason=payload.reason,
    )
    db.add(entitlement)
    await db.flush()
    await _write_offering_event(
        db,
        entitlement=entitlement,
        tenant=tenant,
        offering=offering,
        principal=principal,
        event_type=PlatformActivityType.OFFERING_GRANTED.value,
        action="GRANT",
        old_value=None,
        new_value=_entitlement_snapshot(entitlement),
        idempotency_key=idempotency_key,
        occurred_at=now,
    )
    await ensure_system_role_page_defaults(db, tenant_id)
    await db.commit()
    return await _entitlement_response(db, tenant_id, entitlement.entitlement_id)


async def transition_offering(
    db: AsyncSession,
    principal: Principal,
    tenant_id: uuid.UUID,
    entitlement_id: uuid.UUID,
    action: str,
    payload: TenantOfferingActionRequest,
    *,
    idempotency_key: str,
) -> repository.OfferingReadModel:
    _require_platform_admin(principal)
    existing_event = await repository.get_event_by_idempotency_key(db, idempotency_key)
    if existing_event is not None:
        if existing_event.tenant_id != tenant_id:
            raise ConflictError(
                "Idempotency-Key was already used for another tenant",
                code="IDEMPOTENCY_KEY_REUSED",
            )
        return await _entitlement_response(db, tenant_id, existing_event.entitlement_id)

    tenant = await repository.get_tenant_for_update(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found", code="TENANT_NOT_FOUND")
    entitlement = await repository.get_entitlement(db, tenant_id, entitlement_id, for_update=True)
    if entitlement is None:
        raise NotFoundError("Offering entitlement not found", code="ENTITLEMENT_NOT_FOUND")
    if entitlement.version != payload.expected_version:
        raise ConflictError(
            "Offering entitlement was modified by someone else — refresh and retry",
            code="ENTITLEMENT_VERSION_CONFLICT",
        )
    offering = await db.get(Offering, entitlement.offering_id)
    if offering is None:
        raise NotFoundError("Offering not found", code="OFFERING_NOT_FOUND")
    now = await _database_now(db)
    if (
        entitlement.status
        in (TenantOfferingStatus.ACTIVE.value, TenantOfferingStatus.SUSPENDED.value)
        and entitlement.ends_at is not None
        and entitlement.ends_at <= now
    ):
        entitlement.status = TenantOfferingStatus.EXPIRED.value
        entitlement.version += 1
        await db.flush()
        raise ConflictError("Offering entitlement has expired", code="OFFERING_EXPIRED")

    old_value = _entitlement_snapshot(entitlement)
    if action == "suspend":
        if entitlement.status != TenantOfferingStatus.ACTIVE.value:
            raise BusinessRuleError("Only an active entitlement can be suspended", code="INVALID_ENTITLEMENT_TRANSITION")
        entitlement.status = TenantOfferingStatus.SUSPENDED.value
        entitlement.suspended_at = now
        if payload.reason is not None:
            entitlement.reason = payload.reason
        event_type = PlatformActivityType.OFFERING_SUSPENDED.value
        audit_action = "SUSPEND"
    elif action == "resume":
        if entitlement.status != TenantOfferingStatus.SUSPENDED.value:
            raise BusinessRuleError("Only a suspended entitlement can be resumed", code="INVALID_ENTITLEMENT_TRANSITION")
        entitlement.status = TenantOfferingStatus.ACTIVE.value
        entitlement.suspended_at = None
        if payload.reason is not None:
            entitlement.reason = payload.reason
        event_type = PlatformActivityType.OFFERING_RESUMED.value
        audit_action = "RESUME"
    elif action == "deactivate":
        if entitlement.status not in (TenantOfferingStatus.ACTIVE.value, TenantOfferingStatus.SUSPENDED.value):
            raise BusinessRuleError("Only an open entitlement can be deactivated", code="INVALID_ENTITLEMENT_TRANSITION")
        if not payload.reason:
            raise BusinessRuleError("A reason is required to deactivate an offering", code="REASON_REQUIRED")
        entitlement.status = TenantOfferingStatus.DEACTIVATED.value
        entitlement.deactivated_at = now
        entitlement.reason = payload.reason
        event_type = PlatformActivityType.OFFERING_DEACTIVATED.value
        audit_action = "DEACTIVATE"
    else:
        raise BusinessRuleError("Unsupported offering action", code="UNSUPPORTED_ENTITLEMENT_ACTION")

    entitlement.updated_by_admin_id = principal.id
    entitlement.version += 1
    new_value = _entitlement_snapshot(entitlement)
    await db.flush()
    await _write_offering_event(
        db,
        entitlement=entitlement,
        tenant=tenant,
        offering=offering,
        principal=principal,
        event_type=event_type,
        action=audit_action,
        old_value=old_value,
        new_value=new_value,
        idempotency_key=idempotency_key,
        occurred_at=now,
    )
    await db.commit()
    return await _entitlement_response(db, tenant_id, entitlement_id)


async def remove_retired_offering(
    db: AsyncSession,
    principal: Principal,
    tenant_id: uuid.UUID,
    entitlement_id: uuid.UUID,
    payload: TenantOfferingRemovalRequest,
) -> None:
    """Permanently remove one deactivated or expired entitlement.

    Entitlement events are intentionally removed by the database's cascade.
    A minimal audit tombstone remains so the destructive admin action is
    attributable without retaining the entitlement itself.
    """

    _require_platform_admin(principal)
    tenant = await repository.get_tenant_for_update(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found", code="TENANT_NOT_FOUND")
    entitlement = await repository.get_entitlement(
        db, tenant_id, entitlement_id, for_update=True
    )
    if entitlement is None:
        raise NotFoundError(
            "Offering entitlement not found", code="ENTITLEMENT_NOT_FOUND"
        )
    if entitlement.version != payload.expected_version:
        raise ConflictError(
            "Offering entitlement was modified by someone else — refresh and retry",
            code="ENTITLEMENT_VERSION_CONFLICT",
        )

    now = await _database_now(db)
    is_expired = (
        entitlement.status
        in (TenantOfferingStatus.ACTIVE.value, TenantOfferingStatus.SUSPENDED.value)
        and entitlement.ends_at is not None
        and entitlement.ends_at <= now
    )
    if (
        entitlement.status
        not in (
            TenantOfferingStatus.DEACTIVATED.value,
            TenantOfferingStatus.EXPIRED.value,
        )
        and not is_expired
    ):
        raise BusinessRuleError(
            "Only a deactivated or expired entitlement can be permanently removed",
            code="ENTITLEMENT_NOT_RETIRED",
        )

    effective_status = (
        TenantOfferingStatus.EXPIRED.value if is_expired else entitlement.status
    )
    retired_at = (
        entitlement.deactivated_at
        if effective_status == TenantOfferingStatus.DEACTIVATED.value
        else entitlement.ends_at
    ) or entitlement.updated_at
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="tenant_offering_entitlement",
        entity_id=entitlement_id,
        action="REMOVE",
        changed_by_user_id=None,
        changed_by_admin_id=principal.id,
        old_value={
            "offering_id": str(entitlement.offering_id),
            "status": effective_status,
            "retired_at": retired_at.isoformat(),
        },
        new_value={
            "removed_at": now.isoformat(),
            "reason": payload.reason,
            "removal_mode": "manual",
        },
    )
    await db.delete(entitlement)
    await db.commit()


async def transition_tenant(
    db: AsyncSession,
    principal: Principal,
    tenant_id: uuid.UUID,
    target_status: TenantStatus,
    payload: TenantStatusActionRequest,
    *,
    idempotency_key: str | None = None,
) -> repository.TenantReadModel:
    _require_platform_admin(principal)
    event_type = (
        PlatformActivityType.TENANT_SUSPENDED.value
        if target_status is TenantStatus.SUSPENDED
        else PlatformActivityType.TENANT_ACTIVATED.value
    )
    request_key = idempotency_key or (
        f"tenant-status:{tenant_id}:{target_status.value}:{payload.expected_version}"
    )
    existing_event = await repository.get_platform_activity_by_idempotency_key(
        db, request_key
    )
    if existing_event is not None:
        if (
            existing_event.tenant_id != tenant_id
            or existing_event.event_type != event_type
        ):
            raise ConflictError(
                "Idempotency-Key was already used for another tenant action",
                code="IDEMPOTENCY_KEY_REUSED",
            )
        return await get_tenant_or_404(db, tenant_id)
    tenant = await repository.get_tenant_for_update(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found", code="TENANT_NOT_FOUND")
    if tenant.version != payload.expected_version:
        raise ConflictError("Tenant was modified by someone else — refresh and retry", code="TENANT_VERSION_CONFLICT")
    if tenant.status == target_status.value:
        return await get_tenant_or_404(db, tenant_id)
    now = await _database_now(db)
    old_value = {"status": tenant.status, "version": tenant.version}
    tenant.status = target_status.value
    tenant.version += 1
    tenant.updated_at = now
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="tenant",
        entity_id=tenant_id,
        action=target_status.value,
        changed_by_user_id=None,
        changed_by_admin_id=principal.id,
        old_value=old_value,
        new_value={"status": tenant.status, "version": tenant.version, "reason": payload.reason},
    )
    db.add(
        PlatformActivityEvent(
            event_type=event_type,
            tenant_id=tenant_id,
            tenant_name_snapshot=tenant.org_name,
            actor_id=principal.id,
            actor_type=PlatformActorType.PLATFORM_ADMIN.value,
            occurred_at=now,
            event_metadata={"reason": payload.reason or "", "version": tenant.version},
            idempotency_key=request_key,
        )
    )
    await db.commit()
    result = await repository.get_tenant_details(db, tenant_id)
    if result is None:
        raise RuntimeError("Tenant could not be reloaded after status transition")
    return result


async def list_offering_catalog(db: AsyncSession) -> list[Offering]:
    return await repository.list_all_offerings(db)


async def list_offering_entitlements(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[repository.OfferingReadModel]:
    return await repository.list_tenant_offerings(db, tenant_id, effective_only=False)


async def list_offering_events(
    db: AsyncSession, tenant_id: uuid.UUID
) -> list[TenantOfferingEvent]:
    return await repository.list_tenant_offering_events(db, tenant_id)


async def reconcile_expired_offerings(db: AsyncSession) -> int:
    now = await _database_now(db)
    result = await db.execute(
        select(TenantOffering)
        .where(
            TenantOffering.status.in_(
                (
                    TenantOfferingStatus.ACTIVE.value,
                    TenantOfferingStatus.SUSPENDED.value,
                )
            ),
            TenantOffering.ends_at.is_not(None),
            TenantOffering.ends_at <= now,
        )
        .with_for_update(skip_locked=True)
    )
    rows = list(result.scalars().all())
    for entitlement in rows:
        tenant = await repository.get_tenant(db, entitlement.tenant_id)
        offering = await db.get(Offering, entitlement.offering_id)
        if tenant is None or offering is None:
            continue
        old_value = _entitlement_snapshot(entitlement)
        entitlement.status = TenantOfferingStatus.EXPIRED.value
        entitlement.version += 1
        new_value = _entitlement_snapshot(entitlement)
        await _write_offering_event(
            db,
            entitlement=entitlement,
            tenant=tenant,
            offering=offering,
            principal=None,
            event_type=PlatformActivityType.OFFERING_EXPIRED.value,
            action="EXPIRE",
            old_value=old_value,
            new_value=new_value,
            idempotency_key=f"offering-expired:{entitlement.entitlement_id}:{entitlement.version}",
            occurred_at=now,
        )
    await db.commit()
    return len(rows)


async def purge_retired_offerings(
    db: AsyncSession,
    *,
    retention_days: int | None = None,
    batch_size: int = 500,
) -> int:
    """Hard-delete retired entitlements after the configured retention period."""

    days = (
        retention_days
        if retention_days is not None
        else get_settings().deactivated_offering_retention_days
    )
    if days < 1:
        raise ValueError("retention_days must be at least 1")
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    now = await _database_now(db)
    cutoff = now - timedelta(days=days)
    result = await db.execute(
        select(TenantOffering)
        .where(
            or_(
                and_(
                    TenantOffering.status
                    == TenantOfferingStatus.DEACTIVATED.value,
                    func.coalesce(
                        TenantOffering.deactivated_at,
                        TenantOffering.updated_at,
                    )
                    <= cutoff,
                ),
                and_(
                    TenantOffering.status == TenantOfferingStatus.EXPIRED.value,
                    func.coalesce(TenantOffering.ends_at, TenantOffering.updated_at)
                    <= cutoff,
                ),
            )
        )
        .order_by(TenantOffering.updated_at, TenantOffering.entitlement_id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    rows = list(result.scalars().all())
    for entitlement in rows:
        retired_at = (
            entitlement.deactivated_at
            if entitlement.status == TenantOfferingStatus.DEACTIVATED.value
            else entitlement.ends_at
        ) or entitlement.updated_at
        await record_audit(
            db,
            tenant_id=entitlement.tenant_id,
            entity_type="tenant_offering_entitlement",
            entity_id=entitlement.entitlement_id,
            action="RETENTION_PURGE",
            changed_by_user_id=None,
            changed_by_admin_id=None,
            old_value={
                "offering_id": str(entitlement.offering_id),
                "status": entitlement.status,
                "retired_at": retired_at.isoformat(),
            },
            new_value={
                "removed_at": now.isoformat(),
                "retired_at": retired_at.isoformat(),
                "retention_days": days,
                "removal_mode": "automatic",
            },
        )
        await db.delete(entitlement)

    await db.commit()
    return len(rows)


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
