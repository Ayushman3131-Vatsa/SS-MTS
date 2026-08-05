from datetime import datetime, timedelta, timezone
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal
from app.core.exceptions import BusinessRuleError
from app.models.audit_log import AuditLog
from app.models.enums import TenantOfferingStatus
from app.models.offering import Offering
from app.models.platform_admin import PlatformAdmin
from app.models.tenant import Tenant
from app.models.tenant_offering import TenantOffering
from app.modules.tenants.repository import (
    get_offering_access_denial_code,
    tenant_has_effective_offering,
)
from app.modules.tenants.service import purge_retired_offerings, remove_retired_offering
from app.schemas.tenant import TenantOfferingGrantRequest, TenantOfferingRemovalRequest


def _window(*, offset: timedelta = timedelta()) -> tuple[datetime, datetime]:
    starts_at = datetime.now(timezone.utc) + offset
    return starts_at, starts_at + timedelta(hours=1)


def test_grant_window_requires_utc_and_future_end() -> None:
    starts_at, ends_at = _window(offset=timedelta(minutes=5))
    request = TenantOfferingGrantRequest(
        offering_id="11111111-1111-4111-8111-111111111111",
        starts_at=starts_at,
        ends_at=ends_at,
        expected_tenant_version=7,
        reason="  Scheduled access  ",
    )
    assert request.starts_at.tzinfo is not None
    assert request.expected_tenant_version == 7
    assert request.reason == "Scheduled access"

    with pytest.raises(ValidationError, match="expressed in UTC"):
        TenantOfferingGrantRequest(
            offering_id=request.offering_id,
            starts_at=starts_at.astimezone(timezone(timedelta(hours=5, minutes=30))),
            ends_at=ends_at.astimezone(timezone(timedelta(hours=5, minutes=30))),
        )

    with pytest.raises(ValidationError, match="ends_at must be later"):
        TenantOfferingGrantRequest(
            offering_id=request.offering_id,
            starts_at=starts_at,
            ends_at=starts_at,
        )


def test_permanent_removal_requires_a_non_blank_reason() -> None:
    with pytest.raises(ValidationError, match="must not be blank"):
        TenantOfferingRemovalRequest(expected_version=1, reason="   ")


async def _seed_retired_entitlement(
    db_session: AsyncSession,
    *,
    status: TenantOfferingStatus,
    retired_at: datetime,
) -> tuple[PlatformAdmin, Tenant, TenantOffering]:
    unique = uuid.uuid4().hex
    admin_id = uuid.uuid4()
    admin = PlatformAdmin(
        admin_id=admin_id,
        name="Retention Test Admin",
        email=f"retention-admin-{unique}@example.test",
        password_hash="test-only",
    )
    tenant = Tenant(
        org_name="Retention Test Tenant",
        tenant_code=f"RETENTION_{unique[:8].upper()}",
        workspace_slug=f"retention-{unique[:12]}",
        subscription_plan="Free",
        status="ACTIVE",
        created_by_admin_id=admin_id,
    )
    offering = Offering(
        code=f"RETENTION_{unique[:12].upper()}",
        display_name="Retention Test Offering",
        description="Retention test offering",
        icon_key="test",
        route_slug=f"retention-{unique[:12]}",
        status="ACTIVE",
        sort_order=100,
    )
    db_session.add_all([admin, tenant, offering])
    await db_session.flush()
    entitlement = TenantOffering(
        tenant_id=tenant.tenant_id,
        offering_id=offering.offering_id,
        licensed_by_admin_id=admin.admin_id,
        status=status.value,
        starts_at=retired_at - timedelta(days=30),
        ends_at=retired_at if status is TenantOfferingStatus.EXPIRED else None,
        deactivated_at=(
            retired_at if status is TenantOfferingStatus.DEACTIVATED else None
        ),
    )
    db_session.add(entitlement)
    await db_session.flush()
    return admin, tenant, entitlement


@pytest.mark.asyncio
async def test_manual_removal_hard_deletes_a_deactivated_entitlement(
    db_session: AsyncSession,
) -> None:
    admin, tenant, entitlement = await _seed_retired_entitlement(
        db_session,
        status=TenantOfferingStatus.DEACTIVATED,
        retired_at=datetime.now(timezone.utc),
    )
    entitlement_id = entitlement.entitlement_id

    await remove_retired_offering(
        db_session,
        Principal(type="admin", id=admin.admin_id, email=admin.email),
        tenant.tenant_id,
        entitlement_id,
        TenantOfferingRemovalRequest(
            expected_version=entitlement.version,
            reason="Duplicate historical record",
        ),
    )

    assert await db_session.get(TenantOffering, entitlement_id) is None
    audit = await db_session.scalar(
        select(AuditLog).where(
            AuditLog.entity_id == entitlement_id,
            AuditLog.action == "REMOVE",
        )
    )
    assert audit is not None
    assert audit.new_value["removal_mode"] == "manual"


@pytest.mark.asyncio
async def test_active_entitlement_cannot_be_permanently_removed(
    db_session: AsyncSession,
) -> None:
    admin, tenant, entitlement = await _seed_retired_entitlement(
        db_session,
        status=TenantOfferingStatus.ACTIVE,
        retired_at=datetime.now(timezone.utc) + timedelta(days=30),
    )

    with pytest.raises(BusinessRuleError, match="Only a deactivated or expired"):
        await remove_retired_offering(
            db_session,
            Principal(type="admin", id=admin.admin_id, email=admin.email),
            tenant.tenant_id,
            entitlement.entitlement_id,
            TenantOfferingRemovalRequest(
                expected_version=entitlement.version,
                reason="Should be rejected",
            ),
        )


@pytest.mark.asyncio
async def test_retention_purge_removes_only_entitlements_older_than_90_days(
    db_session: AsyncSession,
) -> None:
    old_retired_at = datetime.now(timezone.utc) - timedelta(days=91)
    recent_retired_at = datetime.now(timezone.utc) - timedelta(days=89)
    _, _, old_entitlement = await _seed_retired_entitlement(
        db_session,
        status=TenantOfferingStatus.DEACTIVATED,
        retired_at=old_retired_at,
    )
    _, _, recent_entitlement = await _seed_retired_entitlement(
        db_session,
        status=TenantOfferingStatus.EXPIRED,
        retired_at=recent_retired_at,
    )
    old_id = old_entitlement.entitlement_id
    recent_id = recent_entitlement.entitlement_id

    assert await purge_retired_offerings(db_session, retention_days=90) == 1
    assert await db_session.get(TenantOffering, old_id) is None
    assert await db_session.get(TenantOffering, recent_id) is not None


@pytest.mark.asyncio
async def test_effective_offering_uses_window_and_ignores_catalog_inactivity(
    db_session: AsyncSession,
) -> None:
    admin_id = uuid.uuid4()
    admin = PlatformAdmin(
        admin_id=admin_id,
        name="Entitlement Test Admin",
        email="entitlement-admin@example.test",
        password_hash="test-only",
    )
    tenant = Tenant(
        org_name="Entitlement Test Tenant",
        tenant_code="ENTITLEMENT_TEST",
        workspace_slug="entitlement-test",
        subscription_plan="Free",
        status="ACTIVE",
        created_by_admin_id=admin_id,
    )
    offering = Offering(
        code="ENTITLEMENT_TEST_OFFERING",
        display_name="Entitlement Test Offering",
        description="Test offering",
        icon_key="test",
        route_slug="entitlement-test-offering",
        status="ACTIVE",
        sort_order=1,
    )
    db_session.add_all([admin, tenant, offering])
    await db_session.flush()

    starts_at, ends_at = _window(offset=timedelta(minutes=-5))
    entitlement = TenantOffering(
        tenant_id=tenant.tenant_id,
        offering_id=offering.offering_id,
        licensed_by_admin_id=admin.admin_id,
        status=TenantOfferingStatus.ACTIVE.value,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    db_session.add(entitlement)
    await db_session.flush()
    assert await tenant_has_effective_offering(
        db_session, tenant.tenant_id, offering.code
    ) is True
    assert await get_offering_access_denial_code(
        db_session, tenant.tenant_id, offering.code
    ) is None

    offering.status = "INACTIVE"
    await db_session.flush()
    assert await tenant_has_effective_offering(
        db_session, tenant.tenant_id, offering.code
    ) is True

    entitlement.status = TenantOfferingStatus.SUSPENDED.value
    await db_session.flush()
    assert await get_offering_access_denial_code(
        db_session, tenant.tenant_id, offering.code
    ) == "OFFERING_SUSPENDED"

    entitlement.ends_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.flush()
    assert await tenant_has_effective_offering(
        db_session, tenant.tenant_id, offering.code
    ) is False
    assert await get_offering_access_denial_code(
        db_session, tenant.tenant_id, offering.code
    ) == "OFFERING_EXPIRED"
