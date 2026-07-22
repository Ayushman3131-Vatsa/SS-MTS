import uuid
from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.common.authz import assert_can_access_task, can_manage_project
from app.common.deps import Principal
from app.core.exceptions import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.models.task import Task
from app.modules.tasks import repository
from app.schemas.task import TaskCreateRequest, TaskUpdateRequest

EMPLOYEE_EDITABLE_FIELDS = {"status", "remarks", "attachment_url"}
INCOMPLETE_CHILD_STATUSES = {"New", "In Progress"}


async def _get_project_or_404(db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID):
    project = await repository.get_project_for_task(db, tenant_id, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    return project


async def create_task(db: AsyncSession, principal: Principal, payload: TaskCreateRequest) -> Task:
    project = await _get_project_or_404(db, principal.tenant_id, payload.project_id)
    if not can_manage_project(principal, project):
        raise ForbiddenError("Only the managing Tenant Admin or Project Manager can create tasks in this project")

    if payload.parent_task_id is not None:
        parent = await repository.get_task(db, principal.tenant_id, payload.parent_task_id)
        if parent is None or parent.project_id != payload.project_id:
            raise NotFoundError("Parent task not found in this project")
        if parent.parent_task_id is not None:
            raise BusinessRuleError("Sub-tasks are limited to one level of depth in this MVP")

    task = Task(tenant_id=principal.tenant_id, **payload.model_dump())
    db.add(task)
    await db.flush()

    await record_audit(
        db,
        tenant_id=principal.tenant_id,
        entity_type="task",
        entity_id=task.task_id,
        action="CREATE",
        changed_by_user_id=principal.id,
        new_value=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(task)
    return task


async def get_task_or_404(db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = await repository.get_task(db, tenant_id, task_id)
    if task is None:
        raise NotFoundError("Task not found")
    return task


async def get_task_for_principal(db: AsyncSession, principal: Principal, task_id: uuid.UUID) -> Task:
    task = await get_task_or_404(db, principal.tenant_id, task_id)
    project = await _get_project_or_404(db, principal.tenant_id, task.project_id)
    assert_can_access_task(principal, task, project)
    return task


async def get_actual_hours(db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID) -> Decimal:
    return await repository.get_actual_hours(db, tenant_id, task_id)


async def list_tasks(db: AsyncSession, principal: Principal, project_id: uuid.UUID | None = None) -> list[Task]:
    if principal.role == "Tenant Admin":
        return await repository.list_tasks_in_tenant(db, principal.tenant_id, project_id)
    if principal.role == "Project Manager":
        return await repository.list_tasks_in_managed_projects(db, principal.tenant_id, principal.id, project_id)
    return await repository.list_tasks_assigned_to(db, principal.tenant_id, principal.id, project_id)


async def update_task(
    db: AsyncSession, principal: Principal, task_id: uuid.UUID, payload: TaskUpdateRequest
) -> Task:
    task = await get_task_or_404(db, principal.tenant_id, task_id)
    project = await _get_project_or_404(db, principal.tenant_id, task.project_id)
    assert_can_access_task(principal, task, project)

    update_fields = payload.model_dump(exclude={"version"}, exclude_unset=True)

    if principal.role == "Employee":
        disallowed = set(update_fields) - EMPLOYEE_EDITABLE_FIELDS
        if disallowed:
            raise ForbiddenError(f"Employees may only update: {', '.join(sorted(EMPLOYEE_EDITABLE_FIELDS))}")

    if update_fields.get("status") == "Completed":
        children = await repository.list_child_tasks(db, principal.tenant_id, task_id)
        if any(child.status in INCOMPLETE_CHILD_STATUSES for child in children):
            raise BusinessRuleError(
                "Cannot mark a parent task Completed while sub-tasks remain New or In Progress"
            )

    old_value = {"status": task.status, "priority": task.priority}

    result = await db.execute(
        update(Task)
        .where(Task.tenant_id == principal.tenant_id, Task.task_id == task_id, Task.version == payload.version)
        .values(**update_fields, version=Task.version + 1)
        .returning(Task)
    )
    updated = result.scalar_one_or_none()
    if updated is None:
        raise ConflictError("Task was modified by someone else — refresh and retry")

    await record_audit(
        db,
        tenant_id=principal.tenant_id,
        entity_type="task",
        entity_id=task_id,
        action="UPDATE",
        changed_by_user_id=principal.id,
        old_value=old_value,
        new_value=payload.model_dump(exclude={"version"}, exclude_unset=True, mode="json"),
    )
    await db.commit()
    await db.refresh(updated)
    return updated
