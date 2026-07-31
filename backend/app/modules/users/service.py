import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.common.deps import Principal
from app.common.roles import assign_role, get_active_role_name, get_role_for_tenant_by_name
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_password, normalize_email, validate_password
from app.models.tenant import Tenant
from app.models.user_account import UserAccount
from app.modules.users import repository
from app.schemas.user import UserCreateRequest, UserResponse, UserUpdateRequest


@dataclass(frozen=True)
class UserView:
    account: UserAccount
    role: str


def to_user_response(view: UserView) -> UserResponse:
    account = view.account
    return UserResponse(
        tenant_id=account.tenant_id,
        user_id=account.id,
        name=account.display_name,
        email=str(account.email),
        role=view.role,
        status=account.status,
        version=account.version,
        created_by_user_id=account.created_by_user_id,
        created_at=account.created_at,
    )


def _assert_tenant_admin(principal: Principal) -> None:
    if principal.type != "user" or principal.tenant_id is None or principal.role != "Tenant Admin":
        raise ForbiddenError("Only a Tenant Admin can provision users")


async def _view_for(db: AsyncSession, account: UserAccount) -> UserView:
    role = await get_active_role_name(db, account.id)
    if role is None:
        raise NotFoundError("User not found")
    return UserView(account=account, role=role)


async def create_user(db: AsyncSession, principal: Principal, payload: UserCreateRequest) -> UserView:
    """Only a Tenant Admin may create Project Manager / Employee users."""
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

    role = await get_role_for_tenant_by_name(db, principal.tenant_id, payload.role)
    if role is None:
        raise NotFoundError(f"Role '{payload.role}' is not configured for this tenant")

    user = UserAccount(
        tenant_id=principal.tenant_id,
        display_name=payload.name,
        email=normalized_email,
        password_hash=hash_password(payload.password),
        created_by_user_id=principal.id,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await assign_role(db, user_id=user.id, role=role, assigned_by=principal.id)

    await record_audit(
        db,
        tenant_id=principal.tenant_id,
        entity_type="user",
        entity_id=user.id,
        action="CREATE",
        changed_by_user_id=principal.id,
        new_value={"name": user.display_name, "email": user.email, "role": payload.role},
    )
    await db.commit()
    await db.refresh(user)
    return UserView(account=user, role=payload.role)


async def list_users(db: AsyncSession, principal: Principal) -> list[UserView]:
    accounts = await repository.list_users(db, principal.tenant_id)
    views: list[UserView] = []
    for account in accounts:
        role = await get_active_role_name(db, account.id)
        if role is not None:
            views.append(UserView(account=account, role=role))
    return views


async def get_user_or_404(db: AsyncSession, principal: Principal, user_id: uuid.UUID) -> UserView:
    user = await repository.get_user(db, principal.tenant_id, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return await _view_for(db, user)


async def update_user(
    db: AsyncSession, principal: Principal, user_id: uuid.UUID, payload: UserUpdateRequest
) -> UserView:
    _assert_tenant_admin(principal)
    current_view = await get_user_or_404(db, principal, user_id)
    current = current_view.account
    old_value = {"name": current.display_name, "status": current.status}

    next_name = payload.name if payload.name is not None else current.display_name
    next_active = current.is_active
    if payload.status is not None:
        next_active = payload.status == "Active"

    result = await db.execute(
        update(UserAccount)
        .where(
            UserAccount.tenant_id == principal.tenant_id,
            UserAccount.id == user_id,
            UserAccount.version == payload.version,
        )
        .values(
            display_name=next_name,
            is_active=next_active,
            version=UserAccount.version + 1,
        )
        .returning(UserAccount)
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
        new_value={"name": updated.display_name, "status": updated.status},
    )
    await db.commit()
    await db.refresh(updated)
    return await _view_for(db, updated)
