import uuid
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.db.session import get_db
from app.models.platform_admin import PlatformAdmin
from app.models.user import User


@dataclass(frozen=True)
class Principal:
    type: Literal["admin", "user"]
    id: uuid.UUID
    email: str
    tenant_id: uuid.UUID | None = None
    role: str | None = None  # 'Tenant Admin' | 'Project Manager' | 'Employee'; None for platform admins


async def get_current_principal(request: Request, db: AsyncSession = Depends(get_db)) -> Principal:
    # JWTGateMiddleware already verified signature/expiry for every non-public
    # route and stashed the claims here; re-verifying identity against the DB
    # on every request means a deactivated user's still-valid token stops
    # working immediately instead of at next expiry.
    claims = getattr(request.state, "jwt_claims", None)
    if claims is None:
        raise UnauthorizedError("Missing authentication context")

    principal_type = claims.get("type")

    if principal_type == "admin":
        admin = await db.get(PlatformAdmin, uuid.UUID(claims["sub"]))
        if admin is None:
            raise UnauthorizedError("Admin account no longer exists")
        return Principal(type="admin", id=admin.admin_id, email=admin.email)

    if principal_type == "user":
        tenant_id = uuid.UUID(claims["tenant_id"])
        user_id = uuid.UUID(claims["sub"])
        user = await db.get(User, {"tenant_id": tenant_id, "user_id": user_id})
        if user is None or user.status != "Active":
            raise UnauthorizedError("User account is inactive or no longer exists")
        return Principal(type="user", id=user.user_id, email=user.email, tenant_id=user.tenant_id, role=user.role)

    raise UnauthorizedError("Unrecognized token type")


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
