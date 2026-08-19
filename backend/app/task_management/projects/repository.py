import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.task_management.models.project import Project
from app.task_management.models.task import Task


async def get_project(db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
    return await db.get(Project, {"tenant_id": tenant_id, "project_id": project_id})


async def list_all_projects(db: AsyncSession, tenant_id: uuid.UUID) -> list[Project]:
    result = await db.execute(select(Project).where(Project.tenant_id == tenant_id))
    return list(result.scalars().all())


async def list_projects_managed_by(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Project]:
    result = await db.execute(
        select(Project).where(
            Project.tenant_id == tenant_id,
            or_(Project.pm_id == user_id, Project.dm_id == user_id),
        )
    )
    return list(result.scalars().all())


async def list_projects_with_assigned_tasks(
    db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> list[Project]:
    result = await db.execute(
        select(Project)
        .join(Task, (Task.tenant_id == Project.tenant_id) & (Task.project_id == Project.project_id))
        .where(
            Project.tenant_id == tenant_id,
            or_(
                Task.assignee_id == user_id,
                Task.technical_lead_id == user_id,
                Task.functional_lead_id == user_id,
            ),
        )
        .distinct()
    )
    return list(result.scalars().all())
