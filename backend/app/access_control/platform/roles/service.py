import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.catalog import role_code, role_response, validate_module_scope
from app.access_control.shared.schemas import RoleCreateRequest, RoleResponse, RoleUpdateRequest
from app.auth.models.platform_role import PlatformRole
from app.auth.models.platform_user_role import PlatformUserRole
from app.common.exceptions import BusinessRuleError, ConflictError, NotFoundError


async def create_platform_role(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    payload: RoleCreateRequest,
) -> RoleResponse:
    del actor_id
    generated = role_code(payload.role_code or payload.role_name)
    existing = await db.execute(select(PlatformRole).where(PlatformRole.role_code == generated))
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("A platform role with this code already exists")
    module_scope = await validate_module_scope(db, realm="platform", module_scope=payload.module_scope)
    role = PlatformRole(
        role_code=generated,
        role_name=payload.role_name,
        description=payload.description,
        module_scope=module_scope,
        is_system=False,
        is_active=True,
    )
    db.add(role)
    await db.flush()
    await db.commit()
    await db.refresh(role)
    return role_response(role)


async def update_platform_role(
    db: AsyncSession,
    *,
    role_id: uuid.UUID,
    payload: RoleUpdateRequest,
) -> RoleResponse:
    role = await db.get(PlatformRole, role_id)
    if role is None:
        raise NotFoundError("Platform role not found")
    if payload.role_name is not None:
        role.role_name = payload.role_name
    if "description" in payload.model_fields_set:
        role.description = payload.description
    await db.commit()
    await db.refresh(role)
    count = await db.scalar(
        select(func.count(PlatformUserRole.id)).where(
            PlatformUserRole.role_id == role.id,
            PlatformUserRole.is_active.is_(True),
        )
    )
    return role_response(role, users_count=int(count or 0))


async def delete_platform_role(db: AsyncSession, *, role_id: uuid.UUID) -> None:
    role = await db.get(PlatformRole, role_id)
    if role is None:
        raise NotFoundError("Platform role not found")
    if role.is_system:
        raise BusinessRuleError("System roles cannot be deleted")
    assigned = await db.scalar(
        select(func.count(PlatformUserRole.id)).where(
            PlatformUserRole.role_id == role.id,
            PlatformUserRole.is_active.is_(True),
        )
    )
    if assigned:
        raise ConflictError("Reassign users before deleting this role")
    await db.delete(role)
    await db.commit()
