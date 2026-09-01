import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.enums import AccessLevel
from app.access_control.shared.resolver import resolve_tenant_page_access

_ACCESS_RANK: dict[AccessLevel, int] = {"none": 0, "view": 1, "modify": 2}


async def tenant_task_management_access_level(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> AccessLevel:
    """Highest task-management access granted to the user across entitled pages."""
    _, page_access = await resolve_tenant_page_access(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    level: AccessLevel = "none"
    for entry in page_access:
        if entry.module != "task_management" and entry.offering_code != "TASK_MANAGEMENT":
            continue
        if _ACCESS_RANK[entry.access_level] > _ACCESS_RANK[level]:
            level = entry.access_level
    return level


async def tenant_has_task_management_view(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    return (
        _ACCESS_RANK[
            await tenant_task_management_access_level(db, tenant_id=tenant_id, user_id=user_id)
        ]
        >= _ACCESS_RANK["view"]
    )


async def tenant_has_task_management_modify(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    return (
        _ACCESS_RANK[
            await tenant_task_management_access_level(db, tenant_id=tenant_id, user_id=user_id)
        ]
        >= _ACCESS_RANK["modify"]
    )
