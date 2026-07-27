import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.common.deps import Principal
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password, normalize_email, validate_password
from app.models.tenant import Tenant
from app.models.user import User
from app.modules.users import repository
from app.schemas.user import UserCreateRequest, UserUpdateRequest


def _assert_tenant_admin(principal: Principal) -> None:
    if principal.type != "user" or principal.tenant_id is None or principal.role != "Tenant Admin":
        raise ForbiddenError("Only a Tenant Admin can provision users")


async def create_user(db: AsyncSession, principal: Principal, payload: UserCreateRequest) -> User:
    """Only a Tenant Admin may create Project Manager / Employee users, and
    only within their own tenant_id. created_by_user_id is always set here."""
    _assert_tenant_admin(principal)

    normalized_email = normalize_email(str(payload.email))
    tenant = await db.get(Tenant, principal.tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")
    validate_password(
        payload.password,
        email=normalized_email,
        name=payload.name,
        org_name=tenant.org_name,
        workspace_slug=tenant.workspace_slug,
    )

    existing = await repository.get_user_by_email(db, principal.tenant_id, normalized_email)
    if existing is not None:
        raise ConflictError("A user with this email already exists in this tenant")

    user = User(
        tenant_id=principal.tenant_id,
        name=payload.name,
        email=normalized_email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        created_by_user_id=principal.id,
    )
    db.add(user)
    await db.flush()

    await record_audit(
        db,
        tenant_id=principal.tenant_id,
        entity_type="user",
        entity_id=user.user_id,
        action="CREATE",
        changed_by_user_id=principal.id,
        new_value={"name": user.name, "email": user.email, "role": user.role},
    )
    await db.commit()
    await db.refresh(user)
    return user


async def list_users(db: AsyncSession, principal: Principal) -> list[User]:
    return await repository.list_users(db, principal.tenant_id)


async def get_user_or_404(db: AsyncSession, principal: Principal, user_id: uuid.UUID) -> User:
    user = await repository.get_user(db, principal.tenant_id, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


async def update_user(
    db: AsyncSession, principal: Principal, user_id: uuid.UUID, payload: UserUpdateRequest
) -> User:
    _assert_tenant_admin(principal)
    current = await get_user_or_404(db, principal, user_id)
    old_value = {"name": current.name, "status": current.status}

    result = await db.execute(
        update(User)
        .where(User.tenant_id == principal.tenant_id, User.user_id == user_id, User.version == payload.version)
        .values(
            name=payload.name if payload.name is not None else current.name,
            status=payload.status if payload.status is not None else current.status,
            version=User.version + 1,
        )
        .returning(User)
    )
    updated = result.scalar_one_or_none()
    if updated is None:
        raise ConflictError("User was modified by someone else — refresh and retry")

    await record_audit(
        db,
        tenant_id=principal.tenant_id,
        entity_type="user",
        entity_id=user_id,
        action="UPDATE",
        changed_by_user_id=principal.id,
        old_value=old_value,
        new_value={"name": updated.name, "status": updated.status},
    )
    await db.commit()
    await db.refresh(updated)
    return updated
