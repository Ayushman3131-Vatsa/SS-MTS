import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.task_management.memberships.model import ProjectMember
from app.modules.task_management.projects.model import Project
from app.modules.task_management.tasks.model import Task


async def get_project(
    db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID, *, for_update: bool = False
) -> Project | None:
    statement = select(Project).where(
        Project.tenant_id == tenant_id,
        Project.project_id == project_id,
    )
    if for_update:
        statement = statement.with_for_update()
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def project_key_exists(db: AsyncSession, tenant_id: uuid.UUID, project_key: str) -> bool:
    result = await db.execute(
        select(Project.project_id)
        .where(Project.tenant_id == tenant_id, Project.project_key == project_key)
        .limit(1)
    )
    return result.first() is not None


async def has_incomplete_tasks(
    db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(Task.task_id)
        .where(
            Task.tenant_id == tenant_id,
            Task.project_id == project_id,
            Task.archived_at.is_(None),
            Task.status.not_in(("Completed", "Cancelled")),
        )
        .limit(1)
    )
    return result.first() is not None


async def list_projects(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    tenant_wide_access: bool,
    page: int,
    page_size: int,
    query: str | None = None,
    status: str | None = None,
    member_id: uuid.UUID | None = None,
    include_archived: bool = False,
    sort: str = "-updated_at",
) -> tuple[list[Project], int]:
    statement = select(Project)
    filters = [Project.tenant_id == tenant_id]

    if not tenant_wide_access:
        statement = statement.join(
            ProjectMember,
            (ProjectMember.tenant_id == Project.tenant_id)
            & (ProjectMember.project_id == Project.project_id)
            & (ProjectMember.user_id == user_id),
        )
    if member_id is not None:
        member_alias = ProjectMember.__table__.alias("filtered_project_member")
        statement = statement.join(
            member_alias,
            (member_alias.c.tenant_id == Project.tenant_id)
            & (member_alias.c.project_id == Project.project_id)
            & (member_alias.c.user_id == member_id),
        )
    if not include_archived:
        filters.append(Project.archived_at.is_(None))
    if query:
        pattern = f"%{query.strip()}%"
        filters.append(
            or_(
                Project.name.ilike(pattern),
                Project.project_key.ilike(pattern),
                Project.description.ilike(pattern),
            )
        )
    if status:
        filters.append(Project.status == status)

    statement = statement.where(*filters).distinct()
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = int((await db.execute(count_statement)).scalar_one())

    sort_columns = {
        "name": Project.name,
        "project_key": Project.project_key,
        "created_at": Project.created_at,
        "updated_at": Project.updated_at,
        "status": Project.status,
    }
    descending = sort.startswith("-")
    sort_column = sort_columns.get(sort.removeprefix("-"), Project.updated_at)
    ordering = sort_column.desc() if descending else sort_column.asc()
    result = await db.execute(
        statement.order_by(ordering, Project.project_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total
