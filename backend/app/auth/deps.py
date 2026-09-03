import uuid
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.platform.users.service import platform_roles_for_admin
from app.access_control.shared.enums import ACCESS_RANK, AccessLevel
from app.access_control.shared.resolver import (
    resolve_platform_page_access,
    resolve_tenant_page_access,
)
from app.auth.models.platform_admin import PlatformAdmin
from app.auth.models.user_account import UserAccount
from app.auth.roles import get_active_role_names
from app.common.db.session import get_db
from app.common.exceptions import ForbiddenError, UnauthorizedError
from app.tenant_management.models.tenant import Tenant
from app.tenant_management.tenants import repository as tenant_repository


@dataclass(frozen=True)
class Principal:
    type: Literal["admin", "user"]
    id: uuid.UUID
    email: str | None
    tenant_id: uuid.UUID | None = None
    role: str | None = None  # primary display role; None for platform admins
    roles: tuple[str, ...] = ()
    tenant_status: str | None = None
    password_change_required: bool = False


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
        if admin is None or not admin.is_active:
            raise UnauthorizedError("Authentication required")
        assigned = await platform_roles_for_admin(db, admin.admin_id)
        role_name = assigned[0].role_name if assigned else "Unassigned"
        return Principal(
            type="admin",
            id=admin.admin_id,
            email=admin.email,
            role=role_name,
            roles=tuple(role.role_name for role in assigned),
            password_change_required=admin.force_pw_reset,
        )

    if principal_type == "user":
        try:
            tenant_id = uuid.UUID(str(claims["tenant_id"]))
            user_id = uuid.UUID(str(claims["sub"]))
        except (KeyError, TypeError, ValueError):
            raise UnauthorizedError("Authentication required") from None
        user = await db.get(UserAccount, user_id)
        tenant = await db.get(Tenant, tenant_id)
        if (
            user is None
            or user.tenant_id != tenant_id
            or not user.is_active
            or tenant is None
        ):
            raise UnauthorizedError("Authentication required")
        if getattr(request.state, "auth_method", None) == "bearer":
            try:
                credential_version = int(claims.get("credential_version", 1))
            except (TypeError, ValueError):
                raise UnauthorizedError("Authentication required") from None
            if credential_version != user.credential_version:
                raise UnauthorizedError("Authentication required")
        role_names = await get_active_role_names(db, user.id)
        role_name = "Tenant Admin" if "Tenant Admin" in role_names else (role_names[0] if role_names else "Unassigned")
        return Principal(
            type="user",
            id=user.id,
            email=user.email,
            tenant_id=user.tenant_id,
            role=role_name,
            roles=tuple(role_names),
            tenant_status=tenant.status,
            password_change_required=user.force_pw_reset,
        )

    raise UnauthorizedError("Authentication required")


async def require_platform_admin(principal: Principal = Depends(get_current_principal)) -> Principal:
    if principal.type != "admin":
        raise ForbiddenError("Platform administrator access required")
    if principal.password_change_required:
        raise ForbiddenError(
            "Password change required",
            code="PASSWORD_CHANGE_REQUIRED",
        )
    return principal


async def require_tenant_user(principal: Principal = Depends(get_current_principal)) -> Principal:
    if principal.type != "user":
        raise ForbiddenError("Tenant user access required")
    if principal.password_change_required:
        raise ForbiddenError(
            "Password change required",
            code="PASSWORD_CHANGE_REQUIRED",
        )
    if principal.tenant_status != "ACTIVE":
        raise ForbiddenError("Tenant access is suspended", code="TENANT_SUSPENDED")
    return principal


def require_roles(*roles: str):
    async def _dependency(principal: Principal = Depends(require_tenant_user)) -> Principal:
        assigned = principal.roles or ((principal.role,) if principal.role else ())
        if not any(role in roles for role in assigned):
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


def require_platform_page_access(page_code: str, minimum: AccessLevel = "modify"):
    """Require a minimum access level (e.g. view or modify) on a platform page."""

    async def _dependency(
        principal: Principal = Depends(require_platform_admin),
        db: AsyncSession = Depends(get_db),
    ) -> Principal:
        _, grants = await resolve_platform_page_access(db, principal.id)
        target = next((g for g in grants if g.page_code == page_code), None)
        current_level: AccessLevel = target.access_level if target else "none"
        if ACCESS_RANK.get(current_level, 0) < ACCESS_RANK.get(minimum, 0):
            raise ForbiddenError(
                f"{minimum.capitalize()} permission required for {page_code}",
                code="INSUFFICIENT_PAGE_ACCESS",
            )
        return principal

    return _dependency


def require_tenant_page_access(page_code: str, minimum: AccessLevel = "modify"):
    """Require a minimum access level (e.g. view or modify) on a tenant page."""

    async def _dependency(
        principal: Principal = Depends(require_tenant_user),
        db: AsyncSession = Depends(get_db),
    ) -> Principal:
        if principal.tenant_id is None:
            raise ForbiddenError("Tenant access required", code="TENANT_REQUIRED")
        _, grants = await resolve_tenant_page_access(
            db, tenant_id=principal.tenant_id, user_id=principal.id
        )
        target = next((g for g in grants if g.page_code == page_code), None)
        current_level: AccessLevel = target.access_level if target else "none"
        if ACCESS_RANK.get(current_level, 0) < ACCESS_RANK.get(minimum, 0):
            raise ForbiddenError(
                f"{minimum.capitalize()} permission required for {page_code}",
                code="INSUFFICIENT_PAGE_ACCESS",
            )
        return principal

    return _dependency
