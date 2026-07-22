import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_progress_log import DailyProgressLog


async def list_logs_for_task(db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID) -> list[DailyProgressLog]:
    result = await db.execute(
        select(DailyProgressLog)
        .where(DailyProgressLog.tenant_id == tenant_id, DailyProgressLog.task_id == task_id)
        .order_by(DailyProgressLog.log_date)
    )
    return list(result.scalars().all())
