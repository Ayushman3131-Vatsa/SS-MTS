import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.task_management.time_entries.model import DailyProgressLog


async def get_entry(db: AsyncSession, tenant_id: uuid.UUID, entry_id: uuid.UUID) -> DailyProgressLog | None:
    return await db.get(DailyProgressLog, {"tenant_id": tenant_id, "log_id": entry_id})


async def list_entries(
    db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[DailyProgressLog], int]:
    filters = (
        DailyProgressLog.tenant_id == tenant_id,
        DailyProgressLog.task_id == task_id,
        DailyProgressLog.deleted_at.is_(None),
    )
    total = int(
        (await db.execute(select(func.count()).select_from(DailyProgressLog).where(*filters))).scalar_one()
    )
    result = await db.execute(
        select(DailyProgressLog)
        .where(*filters)
        .order_by(DailyProgressLog.work_date.desc(), DailyProgressLog.log_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total

