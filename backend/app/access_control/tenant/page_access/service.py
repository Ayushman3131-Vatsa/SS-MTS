import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.catalog import (
    page_access_response,
    pages_in_module_scope,
    tenant_pages_for_entitlements,
)
from app.access_control.shared.enums import AccessLevel
from app.access_control.shared.schemas import PageAccessResponse, PageAccessUpdateRequest
from app.auth.models.role import Role
from app.auth.models.role_page_access import RolePageAccess
from app.common.audit import record_audit
from app.common.exceptions import NotFoundError


async def get_tenant_role_page_access(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    role_id: uuid.UUID,
) -> list[PageAccessResponse]:
    role = await db.get(Role, role_id)
    if role is None or role.tenant_id != tenant_id:
        raise NotFoundError("Tenant role not found")
    pages = pages_in_module_scope(
        await tenant_pages_for_entitlements(db, tenant_id),
        role.module_scope,
        realm="tenant",
    )
    access = await db.execute(select(RolePageAccess).where(RolePageAccess.role_id == role_id))
    by_page_id = {row.page_id: row.access_level for row in access.scalars().all()}
    return [page_access_response(page, by_page_id.get(page.id, "none")) for page in pages]


async def save_tenant_role_page_access(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    role_id: uuid.UUID,
    payload: PageAccessUpdateRequest,
) -> list[PageAccessResponse]:
    role = await db.get(Role, role_id)
    if role is None or role.tenant_id != tenant_id:
        raise NotFoundError("Tenant role not found")
    valid_page_ids = {
        page.id
        for page in pages_in_module_scope(
            await tenant_pages_for_entitlements(db, tenant_id),
            role.module_scope,
            realm="tenant",
        )
    }
    for entry in payload.entries:
        if entry.page_id not in valid_page_ids:
            raise NotFoundError("One or more tenant pages were not found")
        await _upsert_tenant_page_access(db, role_id, entry.page_id, entry.access_level, actor_id)
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="role",
        entity_id=role_id,
        action="UPDATE_PAGE_ACCESS",
        changed_by_user_id=actor_id,
        new_value={"entries": [entry.model_dump(mode="json") for entry in payload.entries]},
    )
    await db.commit()
    return await get_tenant_role_page_access(db, tenant_id=tenant_id, role_id=role_id)


async def _upsert_tenant_page_access(
    db: AsyncSession,
    role_id: uuid.UUID,
    page_id: uuid.UUID,
    access_level: AccessLevel,
    actor_id: uuid.UUID,
) -> None:
    existing = await db.execute(
        select(RolePageAccess).where(
            RolePageAccess.role_id == role_id,
            RolePageAccess.page_id == page_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row is None:
        db.add(
            RolePageAccess(
                role_id=role_id,
                page_id=page_id,
                access_level=access_level,
                updated_by=actor_id,
            )
        )
        return
    await db.execute(
        update(RolePageAccess)
        .where(RolePageAccess.id == row.id)
        .values(access_level=access_level, updated_by=actor_id)
    )
