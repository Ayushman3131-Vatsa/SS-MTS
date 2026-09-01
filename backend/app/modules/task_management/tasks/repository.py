import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, String, cast, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.task_management.memberships.model import ProjectMember
from app.modules.task_management.projects.model import Project
from app.modules.task_management.tasks.model import Task, TaskLink
from app.modules.task_management.time_entries.model import DailyProgressLog


@dataclass(frozen=True)
class TaskReadModel:
    task: Task
    project_key: str
    actual_hours: Decimal


def _actual_hours_subquery():
    return (
        select(func.coalesce(func.sum(DailyProgressLog.hours_worked), 0))
        .where(
            DailyProgressLog.tenant_id == Task.tenant_id,
            DailyProgressLog.task_id == Task.task_id,
            DailyProgressLog.deleted_at.is_(None),
        )
        .correlate(Task)
        .scalar_subquery()
    )


def _read_statement() -> Select:
    return select(Task, Project.project_key, _actual_hours_subquery().label("actual_hours")).join(
        Project,
        (Project.tenant_id == Task.tenant_id) & (Project.project_id == Task.project_id),
    )


def _to_read_models(rows) -> list[TaskReadModel]:
    return [
        TaskReadModel(
            task=row[0],
            project_key=row[1],
            actual_hours=Decimal(row[2] if row[2] is not None else 0),
        )
        for row in rows
    ]


async def get_task(
    db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID, *, for_update: bool = False
) -> Task | None:
    statement = select(Task).where(Task.tenant_id == tenant_id, Task.task_id == task_id)
    if for_update:
        statement = statement.with_for_update()
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def get_task_read_model(
    db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID
) -> TaskReadModel | None:
    result = await db.execute(
        _read_statement().where(Task.tenant_id == tenant_id, Task.task_id == task_id)
    )
    row = result.one_or_none()
    return _to_read_models([row])[0] if row is not None else None


async def allocate_task_number(
    db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID
) -> int:
    result = await db.execute(
        update(Project)
        .where(Project.tenant_id == tenant_id, Project.project_id == project_id)
        .values(next_task_number=Project.next_task_number + 1)
        .returning(Project.next_task_number - 1)
    )
    number = result.scalar_one_or_none()
    if number is None:
        raise NotFoundError("Project disappeared while allocating a task number")
    return int(number)


async def list_tasks(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    tenant_wide_access: bool,
    page: int,
    page_size: int,
    project_id: uuid.UUID | None = None,
    query: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    task_type: str | None = None,
    assignee_id: uuid.UUID | None = None,
    reporter_id: uuid.UUID | None = None,
    member_id: uuid.UUID | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    archived: bool | None = None,
    include_archived: bool = False,
    sort: str = "-updated_at",
) -> tuple[list[TaskReadModel], int]:
    statement = _read_statement()
    filters = [Task.tenant_id == tenant_id]
    if not tenant_wide_access:
        statement = statement.join(
            ProjectMember,
            (ProjectMember.tenant_id == Task.tenant_id)
            & (ProjectMember.project_id == Task.project_id)
            & (ProjectMember.user_id == user_id),
        )
    if member_id is not None:
        member_alias = ProjectMember.__table__.alias("task_filtered_project_member")
        statement = statement.join(
            member_alias,
            (member_alias.c.tenant_id == Task.tenant_id)
            & (member_alias.c.project_id == Task.project_id)
            & (member_alias.c.user_id == member_id),
        )
    if archived is True:
        filters.append(Task.archived_at.is_not(None))
    elif archived is False or not include_archived:
        filters.extend([Task.archived_at.is_(None), Project.archived_at.is_(None)])
    if project_id:
        filters.append(Task.project_id == project_id)
    if query:
        pattern = f"%{query.strip()}%"
        display_key = Project.project_key + "-" + cast(Task.task_number, String)
        filters.append(
            or_(
                Task.name.ilike(pattern),
                Task.description.ilike(pattern),
                display_key.ilike(pattern),
            )
        )
    if status:
        filters.append(Task.status == status)
    if priority:
        filters.append(Task.priority == priority)
    if task_type:
        filters.append(Task.task_type == task_type)
    if assignee_id:
        filters.append(Task.assignee_id == assignee_id)
    if reporter_id:
        filters.append(Task.reporter_id == reporter_id)
    if due_from:
        filters.append(Task.end_date >= due_from)
    if due_to:
        filters.append(Task.end_date <= due_to)

    statement = statement.where(*filters).distinct()
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = int((await db.execute(count_statement)).scalar_one())

    sort_columns = {
        "task_number": Task.task_number,
        "name": Task.name,
        "created_at": Task.created_at,
        "updated_at": Task.updated_at,
        "due_date": Task.end_date,
        "status": Task.status,
        "priority": Task.priority,
    }
    descending = sort.startswith("-")
    sort_column = sort_columns.get(sort.removeprefix("-"), Task.updated_at)
    ordering = sort_column.desc().nulls_last() if descending else sort_column.asc().nulls_last()
    result = await db.execute(
        statement.order_by(ordering, Task.task_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return _to_read_models(result.all()), total


async def list_child_tasks(
    db: AsyncSession, tenant_id: uuid.UUID, parent_task_id: uuid.UUID
) -> list[Task]:
    result = await db.execute(
        select(Task).where(
            Task.tenant_id == tenant_id,
            Task.parent_task_id == parent_task_id,
        )
    )
    return list(result.scalars().all())


async def list_links(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[TaskLink], int]:
    filters = (
        TaskLink.tenant_id == tenant_id,
        or_(TaskLink.source_task_id == task_id, TaskLink.target_task_id == task_id),
    )
    total = int(
        (
            await db.execute(
                select(func.count()).select_from(TaskLink).where(*filters)
            )
        ).scalar_one()
    )
    result = await db.execute(
        select(TaskLink)
        .where(*filters)
        .order_by(TaskLink.created_at, TaskLink.link_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), total


async def get_link(db: AsyncSession, tenant_id: uuid.UUID, link_id: uuid.UUID) -> TaskLink | None:
    return await db.get(TaskLink, {"tenant_id": tenant_id, "link_id": link_id})


async def get_block_link(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    source_task_id: uuid.UUID,
    target_task_id: uuid.UUID,
) -> TaskLink | None:
    result = await db.execute(
        select(TaskLink).where(
            TaskLink.tenant_id == tenant_id,
            TaskLink.source_task_id == source_task_id,
            TaskLink.target_task_id == target_task_id,
            TaskLink.link_type == "BLOCKS",
        )
    )
    return result.scalar_one_or_none()


async def would_create_block_cycle(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    source_task_id: uuid.UUID,
    target_task_id: uuid.UUID,
) -> bool:
    # BLOCKS is directed source -> target. A path target -> source would close a cycle.
    closure = select(TaskLink.target_task_id.label("task_id")).where(
        TaskLink.tenant_id == tenant_id,
        TaskLink.source_task_id == target_task_id,
        TaskLink.link_type == "BLOCKS",
    ).cte("block_closure", recursive=True)
    step = select(TaskLink.target_task_id).join(
        closure,
        (TaskLink.tenant_id == tenant_id)
        & (TaskLink.source_task_id == closure.c.task_id)
        & (TaskLink.link_type == "BLOCKS"),
    )
    closure = closure.union(step)
    result = await db.execute(
        select(closure.c.task_id).where(closure.c.task_id == source_task_id).limit(1)
    )
    return result.first() is not None
