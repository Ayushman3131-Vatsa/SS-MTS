import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.schemas import PageAccessResponse, PageResponse, RoleResponse
from app.auth.models.page import Page
from app.auth.models.platform_role import PlatformRole
from app.auth.models.role import Role
from app.common.exceptions import BusinessRuleError
from app.tenant_management.tenants import repository as tenant_repository

# Tenant pages that are always available regardless of purchased offerings.
CORE_MODULE_SCOPE = "CORE"

CORE_TENANT_PAGE_CODES = frozenset(
    {
        "TENANT_OVERVIEW",
        "TENANT_USERS",
        "TENANT_ROLES",
        "TENANT_CONFIGURATIONS",
    }
)


def role_code(name: str) -> str:
    code = re.sub(r"[^A-Z0-9]+", "_", name.strip().upper()).strip("_")
    return code or "CUSTOM_ROLE"


def role_response(role: Role | PlatformRole, users_count: int = 0) -> RoleResponse:
    return RoleResponse(
        role_id=role.id,
        role_code=role.role_code,
        role_name=role.role_name,
        description=role.description,
        is_system=role.is_system,
        is_active=role.is_active,
        module_scope=getattr(role, "module_scope", None),
        users_count=users_count,
        created_at=role.created_at,
    )


def page_response(page: Page) -> PageResponse:
    return PageResponse(
        page_id=page.id,
        page_code=page.page_code,
        module=page.module,
        page_name=page.page_name,
        route=page.route,
        app_scope=page.app_scope,
        offering_code=page.offering_code,
    )


def page_access_response(page: Page, access_level: str) -> PageAccessResponse:
    return PageAccessResponse(page=page_response(page), access_level=access_level)


async def pages_for_realm(db: AsyncSession, realm: str) -> list[Page]:
    scopes = ["platform"] if realm == "platform" else ["tenant"]
    result = await db.execute(
        select(Page)
        .where(Page.app_scope.in_(scopes), Page.is_active.is_(True))
        .order_by(Page.module, Page.page_name)
    )
    return list(result.scalars().all())


async def entitled_offering_codes(db: AsyncSession, tenant_id: uuid.UUID) -> set[str]:
    offerings = await tenant_repository.list_tenant_offerings(db, tenant_id)
    return {offering.code for offering in offerings}


def page_is_entitled(page: Page, entitled_codes: set[str]) -> bool:
    if page.page_code in CORE_TENANT_PAGE_CODES:
        return True
    if page.offering_code is None:
        return False
    return page.offering_code in entitled_codes


CORE_TENANT_MODULE_SCOPES = frozenset({"CORE", "user_access_management", "tenant_administration"})


def pages_in_module_scope(pages: list[Page], module_scope: str | None, *, realm: str) -> list[Page]:
    if not module_scope:
        return pages
    if realm == "platform":
        return [page for page in pages if page.module == module_scope]
    if module_scope == CORE_MODULE_SCOPE:
        return [page for page in pages if page.page_code in CORE_TENANT_PAGE_CODES]
    return [
        page for page in pages
        if page.offering_code == module_scope or page.module == module_scope
    ]


async def validate_module_scope(
    db: AsyncSession,
    *,
    realm: str,
    module_scope: str | None,
    tenant_id: uuid.UUID | None = None,
) -> str | None:
    if not module_scope:
        return None
    if realm == "platform":
        modules = {page.module for page in await pages_for_realm(db, "platform")}
        if module_scope not in modules:
            raise BusinessRuleError("Select a valid module")
        return module_scope
    if module_scope in CORE_TENANT_MODULE_SCOPES:
        return module_scope
    if tenant_id is None:
        raise BusinessRuleError("Select a subscribed module")
    entitled = await entitled_offering_codes(db, tenant_id)
    if module_scope not in entitled:
        raise BusinessRuleError("Select a subscribed module")
    return module_scope


async def tenant_pages_for_entitlements(db: AsyncSession, tenant_id: uuid.UUID) -> list[Page]:
    entitled = await entitled_offering_codes(db, tenant_id)
    return [page for page in await pages_for_realm(db, "tenant") if page_is_entitled(page, entitled)]
