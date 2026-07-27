import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task_comment import TaskComment


async def list_comments_for_task(db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID) -> list[TaskComment]:
    result = await db.execute(
        select(TaskComment)
        .where(TaskComment.tenant_id == tenant_id, TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at)
    )
    return list(result.scalars().all())
