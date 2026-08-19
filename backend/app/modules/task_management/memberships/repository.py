import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.modules.task_management.memberships.model import ProjectMember
from app.modules.task_management.tasks.model import Task


async def get_member(
    db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID, user_id: uuid.UUID
) -> ProjectMember | None:
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.tenant_id == tenant_id,
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def get_membership(
    db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID, membership_id: uuid.UUID
) -> ProjectMember | None:
    return await db.get(
        ProjectMember,
        {"tenant_id": tenant_id, "membership_id": membership_id},
    )


async def list_members(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[ProjectMember], int]:
    filters = (
        ProjectMember.tenant_id == tenant_id,
        ProjectMember.project_id == project_id,
    )
    total = int(
        (
            await db.execute(
                select(func.count()).select_from(ProjectMember).where(*filters)
            )
        ).scalar_one()
    )
    result = await db.execute(
        select(ProjectMember)
        .where(*filters)
        .order_by(ProjectMember.role, ProjectMember.created_at, ProjectMember.membership_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def get_user(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
    return await db.get(User, {"tenant_id": tenant_id, "user_id": user_id})


async def has_active_assignments(
    db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(Task.task_id)
        .where(
            Task.tenant_id == tenant_id,
            Task.project_id == project_id,
            Task.assignee_id == user_id,
            Task.archived_at.is_(None),
            Task.status.not_in(("Completed", "Cancelled")),
        )
        .limit(1)
    )
    return result.first() is not None
