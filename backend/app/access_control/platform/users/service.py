import uuid

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.platform.schemas import (
    PlatformUserCreateRequest,
    PlatformUserResponse,
    PlatformUserUpdateRequest,
)
from app.access_control.shared.catalog import role_response
from app.auth.models.platform_admin import PlatformAdmin
from app.auth.models.platform_role import PlatformRole
from app.auth.models.platform_user_role import PlatformUserRole
from app.auth.models.user_session import UserSession
from app.auth.first_admin import generate_temporary_password
from app.auth.username_identity import reserve_platform_username
from app.common.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.common.security import hash_password, normalize_email, validate_password


async def platform_roles_for_admin(db: AsyncSession, admin_id: uuid.UUID) -> list[PlatformRole]:
    result = await db.execute(
        select(PlatformRole)
        .join(PlatformUserRole, PlatformUserRole.role_id == PlatformRole.id)
        .where(
            PlatformUserRole.admin_id == admin_id,
            PlatformUserRole.is_active.is_(True),
            PlatformRole.is_active.is_(True),
        )
        .order_by(PlatformRole.role_name)
    )
    return list(result.scalars().all())


async def load_platform_roles(db: AsyncSession, role_ids: list[uuid.UUID]) -> list[PlatformRole]:
    if not role_ids:
        return []
    result = await db.execute(
        select(PlatformRole).where(
            PlatformRole.id.in_(role_ids),
            PlatformRole.is_active.is_(True),
        )
    )
    roles = list(result.scalars().all())
    if len({role.id for role in roles}) != len(set(role_ids)):
        raise NotFoundError("One or more platform roles were not found")
    return roles


def _identity_conflict(exc: IntegrityError) -> ConflictError:
    detail = str(getattr(exc, "orig", exc)).lower()
    if "employee_id" in detail:
        return ConflictError("This employee ID is already in use")
    if "username" in detail:
        return ConflictError("This username is already in use")
    if "email" in detail:
        return ConflictError("This email is already in use")
    return ConflictError("This user could not be saved")


def platform_user_response(
    user: PlatformAdmin,
    roles: list[PlatformRole],
    *,
    temporary_password: str | None = None,
) -> PlatformUserResponse:
    return PlatformUserResponse(
        admin_id=user.admin_id,
        name=user.name,
        username=str(user.username),
        email=str(user.email),
        employee_id=user.employee_id,
        roles=[role_response(role) for role in roles],
        is_active=user.is_active,
        failed_login_count=user.failed_login_count,
        locked_until=user.locked_until,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        temporary_password=temporary_password,
    )


async def list_platform_users(db: AsyncSession) -> list[PlatformUserResponse]:
    result = await db.execute(select(PlatformAdmin).order_by(PlatformAdmin.name))
    users = list(result.scalars().all())
    responses: list[PlatformUserResponse] = []
    for user in users:
        roles = await platform_roles_for_admin(db, user.admin_id)
        responses.append(platform_user_response(user, roles))
    return responses


async def create_platform_user(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    payload: PlatformUserCreateRequest,
) -> PlatformUserResponse:
    normalized_email = normalize_email(str(payload.email))
    existing = await db.execute(select(PlatformAdmin).where(PlatformAdmin.email == normalized_email))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("A platform user with this email already exists")
    username = await reserve_platform_username(db, payload.username)

    roles = await load_platform_roles(db, payload.role_ids)
    temporary_password = payload.password or generate_temporary_password(
        email=normalized_email,
        name=str(payload.name),
        org_name="Platform",
    )
    validate_password(temporary_password, email=normalized_email, name=str(payload.name))
    user = PlatformAdmin(
        name=str(payload.name),
        username=username,
        email=normalized_email,
        employee_id=payload.employee_id,
        password_hash=hash_password(temporary_password),
        force_pw_reset=True,
    )
    db.add(user)
    try:
        await db.flush()
        for role in roles:
            db.add(PlatformUserRole(admin_id=user.admin_id, role_id=role.id, assigned_by=actor_id))
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _identity_conflict(exc) from exc
    await db.refresh(user)
    return platform_user_response(user, roles, temporary_password=temporary_password)


async def update_platform_user(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    admin_id: uuid.UUID,
    payload: PlatformUserUpdateRequest,
) -> PlatformUserResponse:
    user = await db.get(PlatformAdmin, admin_id)
    if user is None:
        raise NotFoundError("Platform user not found")
    if payload.is_active is False and admin_id == actor_id:
        raise BusinessRuleError("You cannot deactivate your own account")
    values: dict[str, object] = {}
    if payload.name is not None:
        values["name"] = payload.name
    if payload.username is not None:
        values["username"] = await reserve_platform_username(
            db, payload.username, exclude_admin_id=admin_id
        )
    if "employee_id" in payload.model_fields_set:
        values["employee_id"] = payload.employee_id
    if payload.is_active is not None:
        values["is_active"] = payload.is_active
        if payload.is_active is False:
            await db.execute(
                update(UserSession)
                .where(
                    UserSession.principal_type == "platform_admin",
                    UserSession.principal_id == admin_id,
                    UserSession.revoked_at.is_(None),
                )
                .values(revoked_at=func.now(), revoked_by="deactivated")
            )
    if values:
        try:
            await db.execute(update(PlatformAdmin).where(PlatformAdmin.admin_id == admin_id).values(**values))
            await db.commit()
        except IntegrityError as exc:
            await db.rollback()
            raise _identity_conflict(exc) from exc
        await db.refresh(user)
    roles = await platform_roles_for_admin(db, user.admin_id)
    return platform_user_response(user, roles)


async def assign_platform_user_roles(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    admin_id: uuid.UUID,
    role_ids: list[uuid.UUID],
) -> PlatformUserResponse:
    user = await db.get(PlatformAdmin, admin_id)
    if user is None:
        raise NotFoundError("Platform user not found")
    roles = await load_platform_roles(db, role_ids)
    await db.execute(delete(PlatformUserRole).where(PlatformUserRole.admin_id == admin_id))
    for role in roles:
        db.add(PlatformUserRole(admin_id=admin_id, role_id=role.id, assigned_by=actor_id))
    await db.commit()
    await db.refresh(user)
    return platform_user_response(user, roles)


async def list_platform_roles(db: AsyncSession) -> list:
    result = await db.execute(
        select(PlatformRole, func.count(PlatformUserRole.id))
        .outerjoin(
            PlatformUserRole,
            (PlatformUserRole.role_id == PlatformRole.id) & (PlatformUserRole.is_active.is_(True)),
        )
        .group_by(PlatformRole.id)
        .order_by(PlatformRole.role_name)
    )
    return [role_response(role, users_count=count) for role, count in result.all()]
