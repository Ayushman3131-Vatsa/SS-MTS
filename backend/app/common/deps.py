import uuid
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.roles import get_active_role_name
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.db.session import get_db
from app.models.platform_admin import PlatformAdmin
from app.models.user_account import UserAccount


@dataclass(frozen=True)
class Principal:
    type: Literal["admin", "user"]
    id: uuid.UUID
    email: str
    tenant_id: uuid.UUID | None = None
    role: str | None = None  # 'Tenant Admin' | 'Project Manager' | 'Employee'; None for platform admins


async def get_current_principal(request: Request, db: AsyncSession = Depends(get_db)) -> Principal:
    # AuthenticationMiddleware has already verified either the bearer token or
    # opaque browser session and stashed a uniform claims shape here. Loading
    # the account again means deletion/deactivation takes effect immediately.
    claims = getattr(request.state, "jwt_claims", None)
    if not isinstance(claims, dict):
        raise UnauthorizedError("Authentication required")

    principal_type = claims.get("type")

    if principal_type == "admin":
        try:
            admin_id = uuid.UUID(str(claims["sub"]))
        except (KeyError, TypeError, ValueError):
            raise UnauthorizedError("Authentication required") from None
        admin = await db.get(PlatformAdmin, admin_id)
        if admin is None:
            raise UnauthorizedError("Authentication required")
        return Principal(type="admin", id=admin.admin_id, email=admin.email)

    if principal_type == "user":
        try:
            tenant_id = uuid.UUID(str(claims["tenant_id"]))
            user_id = uuid.UUID(str(claims["sub"]))
        except (KeyError, TypeError, ValueError):
            raise UnauthorizedError("Authentication required") from None
        user = await db.get(UserAccount, user_id)
        if user is None or user.tenant_id != tenant_id or not user.is_active:
            raise UnauthorizedError("Authentication required")
        role_name = await get_active_role_name(db, user.id)
        if role_name is None:
            raise UnauthorizedError("Authentication required")
        return Principal(
            type="user",
            id=user.id,
            email=user.email,
            tenant_id=user.tenant_id,
            role=role_name,
        )

    raise UnauthorizedError("Authentication required")


async def require_platform_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    if principal.type != "admin":
        raise ForbiddenError("Platform administrator access required")
    return principal


async def require_tenant_user(principal: Principal = Depends(get_current_principal)) -> Principal:
    if principal.type != "user":
        raise ForbiddenError("Tenant user access required")
    return principal


def require_roles(*roles: str):
    async def _dependency(principal: Principal = Depends(require_tenant_user)) -> Principal:
        if principal.role not in roles:
            raise ForbiddenError(f"Requires one of roles: {', '.join(roles)}")
        return principal

    return _dependency
