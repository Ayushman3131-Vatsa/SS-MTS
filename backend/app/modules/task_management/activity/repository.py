import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.task_management.activity.model import TaskActivityEvent


async def list_activity(
    db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[TaskActivityEvent], int]:
    filters = (
        TaskActivityEvent.tenant_id == tenant_id,
        TaskActivityEvent.task_id == task_id,
    )
    total = int(
        (await db.execute(select(func.count()).select_from(TaskActivityEvent).where(*filters))).scalar_one()
    )
    result = await db.execute(
        select(TaskActivityEvent)
        .where(*filters)
        .order_by(TaskActivityEvent.occurred_at, TaskActivityEvent.event_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total
