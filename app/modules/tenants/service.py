import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.common.deps import Principal
from app.core.exceptions import NotFoundError
from app.core.security import hash_password
from app.models.tenant import Tenant
from app.models.user import User
from app.modules.tenants import repository
from app.schemas.tenant import TenantCreateRequest


async def create_tenant(db: AsyncSession, principal: Principal, payload: TenantCreateRequest) -> Tenant:
    """Only a platform_admins row can insert into tenants. In the same
    transaction, seeds the first users row with role='Tenant Admin' and
    created_by_user_id=NULL, per the onboarding rule in the architecture doc."""
    tenant = Tenant(
        org_name=payload.org_name,
        subscription_plan=payload.subscription_plan,
        created_by_admin_id=principal.id,
    )
    db.add(tenant)
    await db.flush()

    tenant_admin = User(
        tenant_id=tenant.tenant_id,
        name=payload.tenant_admin_name,
        email=payload.tenant_admin_email,
        password_hash=hash_password(payload.tenant_admin_password),
        role="Tenant Admin",
        created_by_user_id=None,
    )
    db.add(tenant_admin)
    await db.flush()

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
        new_value={"org_name": tenant.org_name, "subscription_plan": tenant.subscription_plan},
    )
    await record_audit(
        db,
        tenant_id=tenant.tenant_id,
        entity_type="user",
        entity_id=tenant_admin.user_id,
        action="CREATE",
        changed_by_user_id=None,
        new_value={"name": tenant_admin.name, "email": tenant_admin.email, "role": tenant_admin.role},
    )

    await db.commit()
    await db.refresh(tenant)
    return tenant


async def get_tenant_or_404(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    tenant = await repository.get_tenant(db, tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")
    return tenant


async def list_tenants(db: AsyncSession) -> list[Tenant]:
    return await repository.list_tenants(db)
