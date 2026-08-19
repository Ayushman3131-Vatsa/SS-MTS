import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.task_management.attachments.model import TaskAttachment


async def get_attachment(
    db: AsyncSession, tenant_id: uuid.UUID, attachment_id: uuid.UUID
) -> TaskAttachment | None:
    return await db.get(
        TaskAttachment, {"tenant_id": tenant_id, "attachment_id": attachment_id}
    )


async def list_attachments(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[TaskAttachment], int]:
    filters = (
        TaskAttachment.tenant_id == tenant_id,
        TaskAttachment.task_id == task_id,
        TaskAttachment.deleted_at.is_(None),
    )
    total = int(
        (
            await db.execute(
                select(func.count()).select_from(TaskAttachment).where(*filters)
            )
        ).scalar_one()
    )
    result = await db.execute(
        select(TaskAttachment)
        .where(*filters)
        .order_by(TaskAttachment.created_at, TaskAttachment.attachment_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def count_active_attachments(
    db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID
) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(TaskAttachment)
        .where(
            TaskAttachment.tenant_id == tenant_id,
            TaskAttachment.task_id == task_id,
            TaskAttachment.deleted_at.is_(None),
        )
    )
    return int(result.scalar_one())
