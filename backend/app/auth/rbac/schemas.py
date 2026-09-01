"""Compatibility shims for the previous combined RBAC module."""

from app.access_control.platform.schemas import (
    PlatformUserCreateRequest,
    PlatformUserResponse,
    PlatformUserRoleAssignmentRequest,
)
from app.access_control.shared.enums import AccessLevel
from app.access_control.shared.schemas import (
    PageAccessResponse,
    PageAccessUpdate,
    PageAccessUpdateRequest,
    PageResponse,
    RoleCreateRequest,
    RoleResponse,
)
from app.access_control.tenant.schemas import TenantUserRoleAssignmentRequest

__all__ = [
    "AccessLevel",
    "PageAccessResponse",
    "PageAccessUpdate",
    "PageAccessUpdateRequest",
    "PageResponse",
    "PlatformUserCreateRequest",
    "PlatformUserResponse",
    "PlatformUserRoleAssignmentRequest",
    "RoleCreateRequest",
    "RoleResponse",
    "TenantUserRoleAssignmentRequest",
]
