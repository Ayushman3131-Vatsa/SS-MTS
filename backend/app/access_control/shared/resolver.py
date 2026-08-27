import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.catalog import (
    pages_for_realm,
    tenant_pages_for_entitlements,
)
from app.access_control.shared.enums import AccessLevel, most_permissive
from app.access_control.shared.schemas import SessionPageAccess
from app.auth.models.page import Page
from app.auth.models.platform_role import PlatformRole
from app.auth.models.platform_role_page_access import PlatformRolePageAccess
from app.auth.models.platform_user_role import PlatformUserRole
from app.auth.models.role import Role
from app.auth.models.role_page_access import RolePageAccess
from app.auth.models.user_role import UserRole


def _session_page_access(page: Page, access_level: AccessLevel) -> SessionPageAccess:
    return SessionPageAccess(
        page_code=page.page_code,
        module=page.module,
        page_name=page.page_name,
        route=page.route,
        access_level=access_level,
        offering_code=page.offering_code,
    )


def union_by_page(
    pages: list[Page],
    grants: list[tuple[uuid.UUID, AccessLevel]],
    *,
    default: AccessLevel = "none",
) -> list[SessionPageAccess]:
    by_page: dict[uuid.UUID, AccessLevel] = {}
    for page_id, level in grants:
        by_page[page_id] = most_permissive(by_page.get(page_id), level)
    return [_session_page_access(page, by_page.get(page.id, default)) for page in pages]


async def resolve_platform_page_access(
    db: AsyncSession,
    admin_id: uuid.UUID,
) -> tuple[list[str], list[SessionPageAccess]]:
    roles_result = await db.execute(
        select(PlatformRole)
        .join(PlatformUserRole, PlatformUserRole.role_id == PlatformRole.id)
        .where(
            PlatformUserRole.admin_id == admin_id,
            PlatformUserRole.is_active.is_(True),
            PlatformRole.is_active.is_(True),
        )
        .order_by(PlatformRole.role_name)
    )
    roles = list(roles_result.scalars().all())
    pages = await pages_for_realm(db, "platform")
    if not roles:
        return [], union_by_page(pages, [])

    grants_result = await db.execute(
        select(PlatformRolePageAccess.page_id, PlatformRolePageAccess.access_level).where(
            PlatformRolePageAccess.role_id.in_([role.id for role in roles])
        )
    )
    grants = [(row.page_id, row.access_level) for row in grants_result.all()]
    return [role.role_name for role in roles], union_by_page(pages, grants)


async def resolve_tenant_page_access(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[list[str], list[SessionPageAccess]]:
    roles_result = await db.execute(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(
            UserRole.user_id == user_id,
            UserRole.is_active.is_(True),
            Role.is_active.is_(True),
            Role.tenant_id == tenant_id,
        )
        .order_by(Role.role_code)
    )
    roles = list(roles_result.scalars().all())
    pages = await tenant_pages_for_entitlements(db, tenant_id)
    if not roles:
        return [], union_by_page(pages, [])

    grants_result = await db.execute(
        select(RolePageAccess.page_id, RolePageAccess.access_level).where(
            RolePageAccess.role_id.in_([role.id for role in roles])
        )
    )
    entitled_ids = {page.id for page in pages}
    grants = [
        (row.page_id, row.access_level)
        for row in grants_result.all()
        if row.page_id in entitled_ids
    ]
    return [role.role_name for role in roles], union_by_page(pages, grants)
