import uuid
from dataclasses import dataclass

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.auth.deps import Principal
from app.auth.email_identity import reserve_new_user_email
from app.auth.first_admin import generate_temporary_password
from app.auth.username_identity import reserve_tenant_username
from app.auth.models.user_session import UserSession
from app.auth.roles import assign_role, get_active_role_names
from app.access_control.tenant.roles.service import load_tenant_roles
from app.common.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.common.security import hash_password, validate_password
from app.tenant_management.models.tenant import Tenant
from app.auth.models.user_account import UserAccount
from app.auth.accounts import repository
from app.auth.schemas.user import UserCreateRequest, UserResponse, UserUpdateRequest


@dataclass(frozen=True)
class UserView:
    account: UserAccount
    role: str
    roles: tuple[str, ...] = ()


def _identity_conflict(exc: IntegrityError) -> ConflictError:
    detail = str(getattr(exc, "orig", exc)).lower()
    if "employee_id" in detail:
        return ConflictError("This employee ID is already in use")
    if "username" in detail:
        return ConflictError("This username is already in use")
    if "email" in detail:
        return ConflictError("This email is already in use")
    return ConflictError("This user could not be saved")


def to_user_response(view: UserView, *, temporary_password: str | None = None) -> UserResponse:
    account = view.account
    role_names = list(view.roles)
    return UserResponse(
        tenant_id=account.tenant_id,
        user_id=account.id,
        name=account.display_name,
        username=str(account.username),
        email=str(account.email),
        employee_id=account.employee_id,
        role=view.role,
        roles=role_names,
        status=account.status,
        version=account.version,
        created_by_user_id=account.created_by_user_id,
        last_login_at=account.last_login_at,
        created_at=account.created_at,
        temporary_password=temporary_password,
    )


def _assert_tenant_admin(principal: Principal) -> None:
    if principal.type != "user" or principal.tenant_id is None:
        raise ForbiddenError("Only a Tenant Admin can provision users")
    assigned = principal.roles or ((principal.role,) if principal.role else ())
    if "Tenant Admin" not in assigned:
        raise ForbiddenError("Only a Tenant Admin can provision users")


async def _view_for(db: AsyncSession, account: UserAccount) -> UserView:
    names = await get_active_role_names(db, account.id)
    if not names:
        return UserView(account=account, role="Unassigned", roles=())
    role = "Tenant Admin" if "Tenant Admin" in names else names[0]
    return UserView(account=account, role=role, roles=tuple(names))


@dataclass(frozen=True)
class CreatedUserView:
    view: UserView
    temporary_password: str


async def create_user(db: AsyncSession, principal: Principal, payload: UserCreateRequest) -> CreatedUserView:
    """Only a Tenant Admin may create tenant users."""
    _assert_tenant_admin(principal)

    normalized_email = await reserve_new_user_email(
        db,
        str(payload.email),
        tenant_id=principal.tenant_id,
    )
    username = await reserve_tenant_username(db, payload.username)
    tenant = await db.get(Tenant, principal.tenant_id)
    if tenant is None:
        raise NotFoundError("Tenant not found")
    temporary_password = payload.password or generate_temporary_password(
        email=normalized_email,
        name=str(payload.name),
        org_name=tenant.org_name,
    )
    validate_password(
        temporary_password,
        email=normalized_email,
        name=payload.name,
        org_name=tenant.org_name,
    )

    user = UserAccount(
        tenant_id=principal.tenant_id,
        display_name=str(payload.name),
        username=username,
        email=normalized_email,
        password_hash=hash_password(temporary_password),
        employee_id=payload.employee_id,
        created_by_user_id=principal.id,
        is_active=True,
        force_pw_reset=True,
    )
    db.add(user)
    try:
        await db.flush()

        assigned_names: list[str] = []
        if payload.role_ids:
            roles = await load_tenant_roles(db, principal.tenant_id, payload.role_ids)
            for role in roles:
                await assign_role(db, user_id=user.id, role=role, assigned_by=principal.id)
                assigned_names.append(role.role_name)
        primary_role = (
            "Tenant Admin"
            if "Tenant Admin" in assigned_names
            else (assigned_names[0] if assigned_names else "Unassigned")
        )

        await record_audit(
            db,
            tenant_id=principal.tenant_id,
            entity_type="user",
            entity_id=user.id,
            action="CREATE",
            changed_by_user_id=principal.id,
            new_value={"name": user.display_name, "username": user.username, "email": user.email, "roles": assigned_names},
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _identity_conflict(exc) from exc
    await db.refresh(user)
    return CreatedUserView(
        view=UserView(account=user, role=primary_role, roles=tuple(assigned_names)),
        temporary_password=temporary_password,
    )


async def list_users(db: AsyncSession, principal: Principal) -> list[UserView]:
    accounts = await repository.list_users(db, principal.tenant_id)
    views: list[UserView] = []
    for account in accounts:
        views.append(await _view_for(db, account))
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
    old_value = {
        "name": current.display_name,
        "username": current.username,
        "status": current.status,
        "employee_id": current.employee_id,
    }

    next_name = payload.name if payload.name is not None else current.display_name
    next_username = current.username
    if payload.username is not None and payload.username != current.username:
        next_username = await reserve_tenant_username(
            db, payload.username, exclude_user_id=user_id
        )
    next_employee_id = (
        payload.employee_id
        if "employee_id" in payload.model_fields_set
        else current.employee_id
    )
    next_active = current.is_active
    if payload.status is not None:
        next_active = payload.status == "Active"
        if not next_active and user_id == principal.id:
            raise ForbiddenError("You cannot deactivate your own account")

    try:
        result = await db.execute(
            update(UserAccount)
            .where(
                UserAccount.tenant_id == principal.tenant_id,
                UserAccount.id == user_id,
                UserAccount.version == payload.version,
            )
            .values(
                display_name=next_name,
                username=next_username,
                employee_id=next_employee_id,
                is_active=next_active,
                version=UserAccount.version + 1,
            )
            .returning(UserAccount)
        )
        updated = result.scalar_one_or_none()
        if updated is None:
            raise ConflictError("User was modified by someone else — refresh and retry")
        await db.flush()
    except ConflictError:
        raise
    except IntegrityError as exc:
        await db.rollback()
        raise _identity_conflict(exc) from exc

    if current.is_active and not next_active:
        await db.execute(
            update(UserSession)
            .where(
                UserSession.principal_type == "tenant_user",
                UserSession.principal_id == user_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=func.now(), revoked_by="deactivated")
        )

    await record_audit(
        db,
        tenant_id=principal.tenant_id,
        entity_type="user",
        entity_id=user_id,
        action="UPDATE",
        changed_by_user_id=principal.id,
        old_value=old_value,
        new_value={"name": updated.display_name, "username": updated.username, "status": updated.status},
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _identity_conflict(exc) from exc
    await db.refresh(updated)
    return await _view_for(db, updated)
