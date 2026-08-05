import uuid
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.db.session import get_db
from app.models.platform_admin import PlatformAdmin
from app.models.tenant import Tenant
from app.models.user import User
from app.modules.tenants import repository as tenant_repository


@dataclass(frozen=True)
class Principal:
    type: Literal["admin", "user"]
    id: uuid.UUID
    email: str
    tenant_id: uuid.UUID | None = None
    role: str | None = None  # 'Tenant Admin' | 'Project Manager' | 'Employee'; None for platform admins
    tenant_status: str | None = None


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
        user = await db.get(User, {"tenant_id": tenant_id, "user_id": user_id})
        tenant = await db.get(Tenant, tenant_id)
        if user is None or user.status != "Active":
            raise UnauthorizedError("Authentication required")
        if tenant is None:
            raise UnauthorizedError("Authentication required")
        return Principal(
            type="user",
            id=user.user_id,
            email=user.email,
            tenant_id=user.tenant_id,
            role=user.role,
            tenant_status=tenant.status,
        )

    raise UnauthorizedError("Authentication required")


async def require_platform_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    if principal.type != "admin":
        raise ForbiddenError("Platform administrator access required")
    return principal


async def require_tenant_user(principal: Principal = Depends(get_current_principal)) -> Principal:
    if principal.type != "user":
        raise ForbiddenError("Tenant user access required")
    if principal.tenant_status != "ACTIVE":
        raise ForbiddenError("Tenant access is suspended", code="TENANT_SUSPENDED")
    return principal


def require_roles(*roles: str):
    async def _dependency(principal: Principal = Depends(require_tenant_user)) -> Principal:
        if principal.role not in roles:
            raise ForbiddenError(f"Requires one of roles: {', '.join(roles)}")
        return principal

    return _dependency


def require_offering(offering_code: str):
    """Require a currently effective offering for a tenant API module."""

    async def _dependency(
        principal: Principal = Depends(require_tenant_user),
        db: AsyncSession = Depends(get_db),
    ) -> Principal:
        if principal.tenant_id is None:
            raise ForbiddenError("Tenant access required", code="TENANT_REQUIRED")
        denial_code = await tenant_repository.get_offering_access_denial_code(
            db, principal.tenant_id, offering_code
        )
        if denial_code is not None:
            raise ForbiddenError(
                f"The {offering_code} offering is not currently available",
                code=denial_code,
            )
        return principal

    return _dependency
