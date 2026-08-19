import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.task_management.comments.model import TaskComment


async def get_comment(db: AsyncSession, tenant_id: uuid.UUID, comment_id: uuid.UUID) -> TaskComment | None:
    return await db.get(TaskComment, {"tenant_id": tenant_id, "comment_id": comment_id})


async def list_comments(
    db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID, page: int, page_size: int
) -> tuple[list[TaskComment], int]:
    filters = (
        TaskComment.tenant_id == tenant_id,
        TaskComment.task_id == task_id,
        TaskComment.deleted_at.is_(None),
    )
    total = int(
        (await db.execute(select(func.count()).select_from(TaskComment).where(*filters))).scalar_one()
    )
    result = await db.execute(
        select(TaskComment)
        .where(*filters)
        .order_by(TaskComment.created_at, TaskComment.comment_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total

