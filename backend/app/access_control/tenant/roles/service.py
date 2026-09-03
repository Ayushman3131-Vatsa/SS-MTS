import asyncio
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.catalog import role_code, role_response, validate_module_scope
from app.access_control.shared.schemas import RoleCreateRequest, RoleResponse, RoleUpdateRequest
from app.auth.models.role import Role
from app.auth.models.user_account import UserAccount
from app.auth.models.user_role import UserRole
from app.common.audit import record_audit
from app.common.email import send_templated_email
from app.common.exceptions import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.tenant_management.models.tenant import Tenant


def require_tenant_context(tenant_id: uuid.UUID | None) -> uuid.UUID:
    if tenant_id is None:
        raise ForbiddenError("Tenant access required")
    return tenant_id


async def list_tenant_roles(db: AsyncSession, tenant_id: uuid.UUID) -> list[RoleResponse]:
    result = await db.execute(
        select(Role, func.count(UserRole.id))
        .outerjoin(UserRole, (UserRole.role_id == Role.id) & (UserRole.is_active.is_(True)))
        .where(Role.tenant_id == tenant_id)
        .group_by(Role.id)
        .order_by(Role.role_name)
    )
    return [role_response(role, users_count=count) for role, count in result.all()]


async def create_tenant_role(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    payload: RoleCreateRequest,
) -> RoleResponse:
    generated = role_code(payload.role_code or payload.role_name)
    existing = await db.execute(
        select(Role).where(Role.tenant_id == tenant_id, Role.role_code == generated)
    )
    if existing.scalar_one_or_none() is not None:
        raise ConflictError("A tenant role with this code already exists")
    module_scope = await validate_module_scope(
        db,
        realm="tenant",
        module_scope=payload.module_scope,
        tenant_id=tenant_id,
    )
    role = Role(
        tenant_id=tenant_id,
        role_code=generated,
        role_name=payload.role_name,
        description=payload.description,
        module_scope=module_scope,
        is_system=False,
        is_active=True,
    )
    db.add(role)
    await db.flush()
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="role",
        entity_id=role.id,
        action="CREATE",
        changed_by_user_id=actor_id,
        new_value={"role_name": role.role_name, "role_code": role.role_code},
    )
    await db.commit()
    await db.refresh(role)
    return role_response(role)


async def update_tenant_role(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    role_id: uuid.UUID,
    payload: RoleUpdateRequest,
) -> RoleResponse:
    role = await db.get(Role, role_id)
    if role is None or role.tenant_id != tenant_id:
        raise NotFoundError("Tenant role not found")
    if payload.role_name is not None:
        role.role_name = payload.role_name
    if "description" in payload.model_fields_set:
        role.description = payload.description
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="role",
        entity_id=role.id,
        action="UPDATE",
        changed_by_user_id=actor_id,
        new_value={"role_name": role.role_name, "description": role.description},
    )
    await db.commit()
    await db.refresh(role)
    return role_response(role)


async def delete_tenant_role(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    role_id: uuid.UUID,
) -> None:
    role = await db.get(Role, role_id)
    if role is None or role.tenant_id != tenant_id:
        raise NotFoundError("Tenant role not found")
    if role.is_system:
        raise BusinessRuleError("System roles cannot be deleted")
    assigned = await db.scalar(
        select(func.count(UserRole.id)).where(
            UserRole.role_id == role.id,
            UserRole.is_active.is_(True),
        )
    )
    if assigned:
        raise ConflictError("Reassign users before deleting this role")
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="role",
        entity_id=role.id,
        action="DELETE",
        changed_by_user_id=actor_id,
        old_value={"role_name": role.role_name, "role_code": role.role_code},
    )
    await db.delete(role)
    await db.commit()


async def load_tenant_roles(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    role_ids: list[uuid.UUID],
) -> list[Role]:
    result = await db.execute(
        select(Role).where(
            Role.tenant_id == tenant_id,
            Role.id.in_(role_ids),
            Role.is_active.is_(True),
        )
    )
    roles = list(result.scalars().all())
    if len({role.id for role in roles}) != len(set(role_ids)):
        raise NotFoundError("One or more tenant roles were not found")
    return roles


async def assign_tenant_user_roles(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    user_id: uuid.UUID,
    role_ids: list[uuid.UUID],
) -> None:
    user = await db.get(UserAccount, user_id)
    if user is None or user.tenant_id != tenant_id:
        raise NotFoundError("User not found")
    roles = await load_tenant_roles(db, tenant_id, role_ids)
    await db.execute(delete(UserRole).where(UserRole.user_id == user_id))
    for role in roles:
        db.add(UserRole(user_id=user_id, role_id=role.id, assigned_by=actor_id))
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="user",
        entity_id=user_id,
        action="ASSIGN_ROLES",
        changed_by_user_id=actor_id,
        new_value={"role_ids": [str(role.id) for role in roles]},
    )
    await db.commit()

    if user.email:
        tenant = await db.get(Tenant, tenant_id)
        role_names = [role.role_name for role in roles]
        if tenant is not None:
            await send_templated_email(
                db,
                tenant_id=tenant_id,
                template_code="tenant_user_role_updated",
                context={
                    "name": user.display_name,
                    "org_name": tenant.org_name,
                    "tenant_code": tenant.tenant_code,
                    "assigned_roles": ", ".join(role_names) if role_names else "Unassigned",
                    "login_url": f"/{tenant.tenant_code}/login",
                },
                to_email=str(user.email),
            )
