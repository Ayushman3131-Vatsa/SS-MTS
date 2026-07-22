import uuid
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_progress_log import DailyProgressLog
from app.models.project import Project
from app.models.task import Task


async def get_task(db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID) -> Task | None:
    return await db.get(Task, {"tenant_id": tenant_id, "task_id": task_id})


async def get_project_for_task(db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
    return await db.get(Project, {"tenant_id": tenant_id, "project_id": project_id})


async def list_tasks_in_tenant(db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID | None) -> list[Task]:
    stmt = select(Task).where(Task.tenant_id == tenant_id)
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_tasks_in_managed_projects(
    db: AsyncSession, tenant_id: uuid.UUID, pm_user_id: uuid.UUID, project_id: uuid.UUID | None
) -> list[Task]:
    stmt = (
        select(Task)
        .join(Project, (Project.tenant_id == Task.tenant_id) & (Project.project_id == Task.project_id))
        .where(
            Task.tenant_id == tenant_id,
            or_(Project.pm_id == pm_user_id, Project.dm_id == pm_user_id),
        )
    )
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_tasks_assigned_to(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID, project_id: uuid.UUID | None
) -> list[Task]:
    stmt = select(Task).where(
        Task.tenant_id == tenant_id,
        or_(Task.assignee_id == user_id, Task.technical_lead_id == user_id, Task.functional_lead_id == user_id),
    )
    if project_id is not None:
        stmt = stmt.where(Task.project_id == project_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_child_tasks(db: AsyncSession, tenant_id: uuid.UUID, parent_task_id: uuid.UUID) -> list[Task]:
    result = await db.execute(select(Task).where(Task.tenant_id == tenant_id, Task.parent_task_id == parent_task_id))
    return list(result.scalars().all())


async def get_actual_hours(db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID) -> Decimal:
    # actual_hours is intentionally not a stored column — always derived from
    # daily_progress_logs, per the architecture doc's "no static column" rule.
    result = await db.execute(
        select(func.coalesce(func.sum(DailyProgressLog.hours_worked), 0)).where(
            DailyProgressLog.tenant_id == tenant_id, DailyProgressLog.task_id == task_id
        )
    )
    return result.scalar_one()
