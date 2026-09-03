"""Backward-compatible imports for feature modules during the package migration.

Authentication dependencies now live under ``app.auth.deps``.  Keeping this
small forwarding module allows older feature routers to use the new security
implementation while their imports are migrated incrementally.
"""

from app.auth.deps import (
    Principal,
    get_current_principal,
    require_offering,
    require_platform_admin,
    require_platform_page_access,
    require_roles,
    require_tenant_page_access,
    require_tenant_user,
)

__all__ = [
    "Principal",
    "get_current_principal",
    "require_offering",
    "require_platform_admin",
    "require_platform_page_access",
    "require_roles",
    "require_tenant_page_access",
    "require_tenant_user",
]
