"""Helpers for tenant system roles and user ↔ role assignment."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models.role import Role
from app.auth.models.system_roles import ROLE_CODE_BY_NAME, ROLE_NAME_BY_CODE, SYSTEM_ROLES
from app.auth.models.user_account import UserAccount
from app.auth.models.user_role import UserRole


async def seed_tenant_system_roles(db: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Role]:
    """Create the three built-in roles for a new tenant. Returns role_code → Role."""
    roles: dict[str, Role] = {}
    for role_code, role_name in SYSTEM_ROLES:
        role = Role(
            tenant_id=tenant_id,
            role_code=role_code,
            role_name=role_name,
            description=f"System role: {role_name}",
            is_system=True,
            is_active=True,
        )
        db.add(role)
        roles[role_code] = role
    await db.flush()
    return roles


async def assign_role(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    role: Role,
    assigned_by: uuid.UUID | None = None,
) -> UserRole:
    link = UserRole(
        user_id=user_id,
        role_id=role.id,
        assigned_by=assigned_by,
        is_active=True,
    )
    db.add(link)
    await db.flush()
    return link


async def get_active_role_name(db: AsyncSession, user_id: uuid.UUID) -> str | None:
    result = await db.execute(
        select(Role.role_name)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            UserRole.is_active.is_(True),
            Role.is_active.is_(True),
        )
        .order_by(Role.role_code)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_role_for_tenant_by_name(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    role_name: str,
) -> Role | None:
    role_code = ROLE_CODE_BY_NAME.get(role_name)
    if role_code is None:
        return None
    result = await db.execute(
        select(Role).where(
            Role.tenant_id == tenant_id,
            Role.role_code == role_code,
            Role.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def load_user_with_role(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[UserAccount, str] | None:
    user = await db.get(UserAccount, user_id)
    if user is None or user.tenant_id != tenant_id:
        return None
    role_name = await get_active_role_name(db, user.id)
    if role_name is None:
        return None
    return user, role_name


__all__ = [
    "ROLE_CODE_BY_NAME",
    "ROLE_NAME_BY_CODE",
    "SYSTEM_ROLES",
    "assign_role",
    "get_active_role_name",
    "get_role_for_tenant_by_name",
    "load_user_with_role",
    "seed_tenant_system_roles",
]
