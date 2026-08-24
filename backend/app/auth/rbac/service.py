from app.access_control.platform.page_access.service import (
    get_platform_role_page_access,
    save_platform_role_page_access,
)
from app.access_control.platform.roles.service import create_platform_role
from app.access_control.platform.users.service import (
    assign_platform_user_roles,
    create_platform_user,
    list_platform_roles,
    list_platform_users,
)
from app.access_control.shared.catalog import page_response, pages_for_realm
from app.access_control.tenant.page_access.service import (
    get_tenant_role_page_access,
    save_tenant_role_page_access,
)
from app.access_control.tenant.roles.service import (
    assign_tenant_user_roles,
    create_tenant_role,
    list_tenant_roles,
    require_tenant_context,
)
from app.auth.rbac.schemas import (
    AccessLevel,
    PageAccessResponse,
    PageAccessUpdateRequest,
    PageResponse,
    PlatformUserCreateRequest,
    RoleCreateRequest,
    RoleResponse,
)


async def list_pages(db, *, realm: str):
    return [page_response(page) for page in await pages_for_realm(db, realm)]


__all__ = [
    "AccessLevel",
    "PageAccessResponse",
    "PageAccessUpdateRequest",
    "PageResponse",
    "PlatformUserCreateRequest",
    "RoleCreateRequest",
    "RoleResponse",
    "assign_platform_user_roles",
    "assign_tenant_user_roles",
    "create_platform_role",
    "create_platform_user",
    "create_tenant_role",
    "get_platform_role_page_access",
    "get_tenant_role_page_access",
    "list_pages",
    "list_platform_roles",
    "list_platform_users",
    "list_tenant_roles",
    "require_tenant_context",
    "save_platform_role_page_access",
    "save_tenant_role_page_access",
]
