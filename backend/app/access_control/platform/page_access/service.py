import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.catalog import page_access_response, pages_for_realm, pages_in_module_scope
from app.access_control.shared.enums import AccessLevel
from app.access_control.shared.schemas import PageAccessResponse, PageAccessUpdateRequest
from app.auth.models.platform_role import PlatformRole
from app.auth.models.platform_role_page_access import PlatformRolePageAccess
from app.common.exceptions import NotFoundError


async def get_platform_role_page_access(
    db: AsyncSession,
    role_id: uuid.UUID,
) -> list[PageAccessResponse]:
    role = await db.get(PlatformRole, role_id)
    if role is None:
        raise NotFoundError("Platform role not found")
    pages = pages_in_module_scope(await pages_for_realm(db, "platform"), role.module_scope, realm="platform")
    access = await db.execute(
        select(PlatformRolePageAccess).where(PlatformRolePageAccess.role_id == role_id)
    )
    by_page_id = {row.page_id: row.access_level for row in access.scalars().all()}
    return [page_access_response(page, by_page_id.get(page.id, "none")) for page in pages]


async def save_platform_role_page_access(
    db: AsyncSession,
    *,
    actor_id: uuid.UUID,
    role_id: uuid.UUID,
    payload: PageAccessUpdateRequest,
) -> list[PageAccessResponse]:
    role = await db.get(PlatformRole, role_id)
    if role is None:
        raise NotFoundError("Platform role not found")
    valid_page_ids = {
        page.id
        for page in pages_in_module_scope(
            await pages_for_realm(db, "platform"), role.module_scope, realm="platform"
        )
    }
    for entry in payload.entries:
        if entry.page_id not in valid_page_ids:
            raise NotFoundError("One or more platform pages were not found")
        await _upsert_platform_page_access(db, role_id, entry.page_id, entry.access_level, actor_id)
    await db.commit()
    return await get_platform_role_page_access(db, role_id)


async def _upsert_platform_page_access(
    db: AsyncSession,
    role_id: uuid.UUID,
    page_id: uuid.UUID,
    access_level: AccessLevel,
    actor_id: uuid.UUID,
) -> None:
    existing = await db.execute(
        select(PlatformRolePageAccess).where(
            PlatformRolePageAccess.role_id == role_id,
            PlatformRolePageAccess.page_id == page_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row is None:
        db.add(
            PlatformRolePageAccess(
                role_id=role_id,
                page_id=page_id,
                access_level=access_level,
                updated_by=actor_id,
            )
        )
        return
    await db.execute(
        update(PlatformRolePageAccess)
        .where(PlatformRolePageAccess.id == row.id)
        .values(access_level=access_level, updated_by=actor_id)
    )
