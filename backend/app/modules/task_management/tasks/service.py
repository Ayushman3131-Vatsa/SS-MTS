import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.common.deps import Principal
from app.core.exceptions import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.modules.task_management.access import (
    assert_can_create_task,
    assert_can_execute_task,
    assert_can_manage_project,
    assert_can_view_project,
    assert_task_is_mutable,
    get_project_or_404,
    project_access,
    require_tenant_principal,
)
from app.modules.task_management.activity.service import record_activity
from app.modules.task_management.domain import errors
from app.modules.task_management.domain.enums import (
    ActivityEventType,
    ProjectMemberRole,
    TaskLinkType,
    TaskStatus,
    TaskType,
)
from app.modules.task_management.domain.policies import can_manage_project
from app.modules.task_management.domain.transitions import can_transition_task
from app.modules.task_management.memberships.service import ensure_member, validate_member_user
from app.modules.task_management.schemas import PageResponse
from app.modules.task_management.tasks import repository
from app.modules.task_management.tasks.model import Task, TaskLink
from app.modules.task_management.tasks.schemas import (
    TaskCreateRequest,
    TaskLinkCreateRequest,
    TaskLinkResponse,
    TaskResponse,
    TaskTransitionRequest,
    TaskUpdateRequest,
)


def to_response(read_model: repository.TaskReadModel) -> TaskResponse:
    task = read_model.task
    return TaskResponse.model_validate(
        {
            **{column.name: getattr(task, column.name) for column in task.__table__.columns},
            "display_key": f"{read_model.project_key}-{task.task_number}",
            "actual_hours": read_model.actual_hours,
        }
    )


async def get_task_or_404(
    db: AsyncSession, principal: Principal, task_id: uuid.UUID, *, for_update: bool = False
) -> Task:
    tenant_id, _, _ = require_tenant_principal(principal)
    task = await repository.get_task(db, tenant_id, task_id, for_update=for_update)
    if task is None:
        raise NotFoundError("Task not found")
    return task


async def _validate_hierarchy(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    task_type: TaskType,
    parent_task_id: uuid.UUID | None,
) -> Task | None:
    parent = None
    if parent_task_id is not None:
        parent = await repository.get_task(db, tenant_id, parent_task_id)
        if parent is None or parent.project_id != project_id or parent.archived_at is not None:
            raise BusinessRuleError(
                "Parent task must be an active task in the same project",
                code=errors.INVALID_TASK_HIERARCHY,
            )
    if task_type == TaskType.EPIC and parent is not None:
        raise BusinessRuleError("Epics cannot have a parent", code=errors.INVALID_TASK_HIERARCHY)
    if task_type == TaskType.SUBTASK:
        if parent is None or parent.task_type not in {
            TaskType.STORY,
            TaskType.TASK,
            TaskType.BUG,
        }:
            raise BusinessRuleError(
                "A subtask requires a Story, Task or Bug parent",
                code=errors.INVALID_TASK_HIERARCHY,
            )
    elif parent is not None and parent.task_type != TaskType.EPIC:
        raise BusinessRuleError(
            "Only Story, Task or Bug items may belong to an Epic",
            code=errors.INVALID_TASK_HIERARCHY,
        )
    return parent


async def _ensure_assignment_member(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    await validate_member_user(db, tenant_id, user_id, ProjectMemberRole.MEMBER)
    await ensure_member(
        db,
        tenant_id=tenant_id,
        project_id=project_id,
        user_id=user_id,
        role=ProjectMemberRole.MEMBER,
        added_by_user_id=actor_id,
    )


async def _validate_blocked_by(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    task_id: uuid.UUID | None,
    blocked_by_id: uuid.UUID | None,
) -> Task | None:
    if blocked_by_id is None:
        return None
    blocker = await repository.get_task(db, tenant_id, blocked_by_id)
    if blocker is None or blocker.project_id != project_id or blocker.archived_at is not None:
        raise BusinessRuleError("Blocking task must be active and in the same project", code=errors.TASK_LINK_CYCLE)
    if task_id is not None and blocked_by_id == task_id:
        raise BusinessRuleError("A task cannot block itself", code=errors.TASK_LINK_CYCLE)
    return blocker


async def create_task(
    db: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID,
    payload: TaskCreateRequest,
    *,
    legacy_attachment_url: str | None = None,
) -> repository.TaskReadModel:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    project = await get_project_or_404(db, principal, project_id)
    if project.archived_at is not None:
        raise BusinessRuleError("Cannot add tasks to an archived project", code="PROJECT_ARCHIVED")
    if project.status in {"Completed", "Cancelled"}:
        raise BusinessRuleError(
            "Reopen the project before adding tasks", code="PROJECT_NOT_ACTIVE"
        )
    access = await assert_can_create_task(db, principal, project_id)
    manager = can_manage_project(access)
    if not manager and any(
        value is not None
        for value in (payload.assignee_id, payload.technical_lead_id, payload.functional_lead_id)
    ):
        raise ForbiddenError("Project members create unassigned tasks; a manager assigns them")
    if payload.status not in {TaskStatus.NEW, TaskStatus.ASSIGNED}:
        raise BusinessRuleError("New tasks must start as New or Assigned", code=errors.INVALID_TASK_TRANSITION)
    if payload.status == TaskStatus.ASSIGNED and payload.assignee_id is None:
        raise BusinessRuleError("Assigned tasks require an assignee", code=errors.INVALID_TASK_TRANSITION)

    await _validate_hierarchy(
        db, tenant_id, project_id, payload.task_type, payload.parent_task_id
    )
    blocker = await _validate_blocked_by(
        db,
        tenant_id=tenant_id,
        project_id=project_id,
        task_id=None,
        blocked_by_id=payload.blocked_by_id,
    )
    for user_id in {
        value
        for value in (
            payload.assignee_id,
            payload.technical_lead_id,
            payload.functional_lead_id,
        )
        if value is not None
    }:
        await _ensure_assignment_member(
            db,
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
            actor_id=actor_id,
        )

    task_number = await repository.allocate_task_number(db, tenant_id, project_id)
    values = payload.model_dump(mode="python")
    if payload.assignee_id is not None and payload.status == TaskStatus.NEW:
        values["status"] = TaskStatus.ASSIGNED
    task = Task(
        tenant_id=tenant_id,
        project_id=project_id,
        task_number=task_number,
        reporter_id=actor_id,
        created_by_user_id=actor_id,
        attachment_url=legacy_attachment_url,
        **values,
    )
    db.add(task)
    await db.flush()

    if blocker is not None:
        db.add(
            TaskLink(
                tenant_id=tenant_id,
                source_task_id=blocker.task_id,
                target_task_id=task.task_id,
                link_type=TaskLinkType.BLOCKS,
                created_by_user_id=actor_id,
            )
        )
    record_activity(
        db,
        tenant_id=tenant_id,
        task_id=task.task_id,
        event_type=ActivityEventType.CREATED,
        actor_user_id=actor_id,
        data={"project_id": str(project_id), "task_number": task_number, "name": task.name},
    )
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="task",
        entity_id=task.task_id,
        action="CREATE",
        changed_by_user_id=actor_id,
        new_value={**payload.model_dump(mode="json"), "task_number": task_number},
    )
    await db.commit()
    read_model = await repository.get_task_read_model(db, tenant_id, task.task_id)
    if read_model is None:
        raise RuntimeError("Task could not be reloaded after creation")
    return read_model


async def list_tasks(
    db: AsyncSession,
    principal: Principal,
    *,
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
    due_from=None,
    due_to=None,
    archived: bool | None = None,
    include_archived: bool = False,
    sort: str = "-updated_at",
) -> PageResponse[TaskResponse]:
    tenant_id, actor_id, tenant_role = require_tenant_principal(principal)
    items, total = await repository.list_tasks(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        tenant_role=tenant_role,
        page=page,
        page_size=page_size,
        project_id=project_id,
        query=query,
        status=status,
        priority=priority,
        task_type=task_type,
        assignee_id=assignee_id,
        reporter_id=reporter_id,
        member_id=member_id,
        due_from=due_from,
        due_to=due_to,
        archived=archived,
        include_archived=include_archived,
        sort=sort,
    )
    return PageResponse[TaskResponse](
        items=[to_response(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


async def list_tasks_legacy(
    db: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID | None = None,
) -> list[repository.TaskReadModel]:
    tenant_id, actor_id, tenant_role = require_tenant_principal(principal)
    items, _ = await repository.list_tasks(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        tenant_role=tenant_role,
        page=1,
        page_size=1_000_000,
        project_id=project_id,
        include_archived=False,
        sort="task_number",
    )
    return items


async def get_task_for_principal(
    db: AsyncSession, principal: Principal, task_id: uuid.UUID
) -> repository.TaskReadModel:
    task = await get_task_or_404(db, principal, task_id)
    await assert_can_view_project(db, principal, task.project_id)
    read_model = await repository.get_task_read_model(db, principal.tenant_id, task_id)
    if read_model is None:
        raise NotFoundError("Task not found")
    return read_model


async def update_task(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    payload: TaskUpdateRequest,
    *,
    legacy_status: TaskStatus | None = None,
    legacy_attachment_url_provided: bool = False,
    legacy_attachment_url: str | None = None,
) -> repository.TaskReadModel:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    task = await get_task_or_404(db, principal, task_id)
    await assert_task_is_mutable(db, principal, task)
    access = await project_access(
        db, principal, task.project_id, is_assignee=task.assignee_id == actor_id
    )
    manager = can_manage_project(access)
    update_fields = payload.model_dump(exclude={"version"}, exclude_unset=True, mode="python")
    if legacy_status is not None:
        if not can_transition_task(task.status, legacy_status.value):
            raise BusinessRuleError(
                f"Task cannot transition from {task.status} to {legacy_status.value}",
                code=errors.INVALID_TASK_TRANSITION,
            )
        if legacy_status == TaskStatus.COMPLETED:
            children = await repository.list_child_tasks(db, tenant_id, task_id)
            if any(child.status not in {TaskStatus.COMPLETED, TaskStatus.CANCELLED} for child in children):
                raise BusinessRuleError(
                    "Cannot complete a parent while active children remain",
                    code=errors.INCOMPLETE_CHILDREN,
                )
        update_fields["status"] = legacy_status
        update_fields["completed_at"] = (
            datetime.now(timezone.utc) if legacy_status == TaskStatus.COMPLETED else None
        )
    if legacy_attachment_url_provided:
        update_fields["attachment_url"] = legacy_attachment_url
    if not update_fields:
        raise BusinessRuleError("Provide at least one task field to update", code="TASK_UPDATE_EMPTY")
    resulting_status = update_fields.get("status", task.status)
    resulting_assignee = update_fields.get("assignee_id", task.assignee_id)
    if resulting_status == TaskStatus.ASSIGNED and resulting_assignee is None:
        raise BusinessRuleError(
            "Assigned status requires an assignee", code=errors.INVALID_TASK_TRANSITION
        )
    if not manager:
        if not access.is_assignee or set(update_fields) - {
            "remarks",
            "attachment_url",
            "status",
            "completed_at",
        }:
            raise ForbiddenError("Only project managers can update task planning fields")

    if {"task_type", "parent_task_id"} & update_fields.keys():
        target_type = TaskType(update_fields.get("task_type", task.task_type))
        target_parent_id = update_fields.get("parent_task_id", task.parent_task_id)
        if target_parent_id == task_id:
            raise BusinessRuleError(
                "A task cannot be its own parent", code=errors.INVALID_TASK_HIERARCHY
            )
        await _validate_hierarchy(
            db,
            tenant_id,
            task.project_id,
            target_type,
            target_parent_id,
        )
        children = await repository.list_child_tasks(db, tenant_id, task_id)
        if target_type == TaskType.EPIC:
            invalid_children = any(
                child.task_type not in {TaskType.STORY, TaskType.TASK, TaskType.BUG}
                for child in children
            )
        elif target_type in {TaskType.STORY, TaskType.TASK, TaskType.BUG}:
            invalid_children = any(
                child.task_type != TaskType.SUBTASK for child in children
            )
        else:
            invalid_children = bool(children)
        if invalid_children:
            raise BusinessRuleError(
                "Task type would make its existing children invalid",
                code=errors.INVALID_TASK_HIERARCHY,
            )

    start_date = update_fields.get("start_date", task.start_date)
    end_date = update_fields.get("end_date", task.end_date)
    if start_date is not None and end_date is not None and end_date < start_date:
        raise BusinessRuleError("end_date must be on or after start_date", code="TASK_DATE_ORDER")

    old_assignee = task.assignee_id
    old_blocked_by = task.blocked_by_id
    old_status = task.status
    if "assignee_id" in update_fields and update_fields["assignee_id"] is not None:
        await _ensure_assignment_member(
            db,
            tenant_id=tenant_id,
            project_id=task.project_id,
            user_id=update_fields["assignee_id"],
            actor_id=actor_id,
        )
    for lead_field in ("technical_lead_id", "functional_lead_id"):
        user_id = update_fields.get(lead_field)
        if user_id is not None:
            await _ensure_assignment_member(
                db,
                tenant_id=tenant_id,
                project_id=task.project_id,
                user_id=user_id,
                actor_id=actor_id,
            )
    if "blocked_by_id" in update_fields:
        blocker = await _validate_blocked_by(
            db,
            tenant_id=tenant_id,
            project_id=task.project_id,
            task_id=task_id,
            blocked_by_id=update_fields["blocked_by_id"],
        )
        if blocker is not None and await repository.would_create_block_cycle(
            db, tenant_id, blocker.task_id, task_id
        ):
            raise BusinessRuleError(
                "Blocking dependency would create a cycle", code=errors.TASK_LINK_CYCLE
            )
    if task.status == TaskStatus.NEW and update_fields.get("assignee_id") is not None:
        update_fields["status"] = TaskStatus.ASSIGNED

    old_value = {field: getattr(task, field) for field in update_fields if hasattr(task, field)}
    result = await db.execute(
        update(Task)
        .where(
            Task.tenant_id == tenant_id,
            Task.task_id == task_id,
            Task.version == payload.version,
        )
        .values(**update_fields, version=Task.version + 1, updated_at=func.now())
        .returning(Task)
    )
    updated = result.scalar_one_or_none()
    if updated is None:
        raise ConflictError("Task was modified by someone else — refresh and retry")

    if "blocked_by_id" in update_fields and update_fields["blocked_by_id"] != old_blocked_by:
        if old_blocked_by is not None:
            old_link = await repository.get_block_link(
                db, tenant_id, old_blocked_by, task_id
            )
            if old_link is not None:
                await db.delete(old_link)
        if update_fields["blocked_by_id"] is not None:
            existing_link = await repository.get_block_link(
                db, tenant_id, update_fields["blocked_by_id"], task_id
            )
            if existing_link is None:
                db.add(
                    TaskLink(
                        tenant_id=tenant_id,
                        source_task_id=update_fields["blocked_by_id"],
                        target_task_id=task_id,
                        link_type=TaskLinkType.BLOCKS,
                        created_by_user_id=actor_id,
                    )
                )

    status_changed = "status" in update_fields and update_fields["status"] != old_status
    assignment_changed = (
        "assignee_id" in update_fields and update_fields["assignee_id"] != old_assignee
    )
    event_type = (
        ActivityEventType.TRANSITIONED
        if status_changed
        else ActivityEventType.ASSIGNED
        if assignment_changed
        else ActivityEventType.UPDATED
    )
    activity_data = {"fields": sorted(update_fields)}
    if status_changed:
        activity_data.update(
            {"from_status": old_status, "to_status": str(update_fields["status"])}
        )
    record_activity(
        db,
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=event_type,
        actor_user_id=actor_id,
        data=activity_data,
    )
    audit_new_value = payload.model_dump(
        exclude={"version"}, exclude_unset=True, mode="json"
    )
    if "status" in update_fields:
        audit_new_value["status"] = str(update_fields["status"])
    if "completed_at" in update_fields:
        completed_at = update_fields["completed_at"]
        audit_new_value["completed_at"] = (
            completed_at.isoformat() if completed_at is not None else None
        )
    if legacy_attachment_url_provided:
        audit_new_value["attachment_url"] = legacy_attachment_url
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="task",
        entity_id=task_id,
        action="UPDATE",
        changed_by_user_id=actor_id,
        old_value={key: str(value) if value is not None else None for key, value in old_value.items()},
        new_value=audit_new_value,
    )
    await db.commit()
    read_model = await repository.get_task_read_model(db, tenant_id, task_id)
    if read_model is None:
        raise RuntimeError("Task could not be reloaded after update")
    return read_model


async def transition_task(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    payload: TaskTransitionRequest,
) -> repository.TaskReadModel:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    task = await get_task_or_404(db, principal, task_id)
    await assert_task_is_mutable(db, principal, task)
    await assert_can_execute_task(db, principal, task)
    if task.version != payload.version:
        raise ConflictError("Task was modified by someone else — refresh and retry")
    old_status = task.status
    target = payload.to_status.value
    if target == TaskStatus.ASSIGNED and task.assignee_id is None:
        raise BusinessRuleError(
            "Assigned status requires an assignee", code=errors.INVALID_TASK_TRANSITION
        )
    if not can_transition_task(task.status, target):
        raise BusinessRuleError(
            f"Task cannot transition from {task.status} to {target}",
            code=errors.INVALID_TASK_TRANSITION,
        )
    if target == task.status:
        current = await repository.get_task_read_model(db, tenant_id, task_id)
        if current is None:
            raise NotFoundError("Task not found")
        return current
    if target == TaskStatus.COMPLETED:
        children = await repository.list_child_tasks(db, tenant_id, task_id)
        if any(child.status not in {TaskStatus.COMPLETED, TaskStatus.CANCELLED} for child in children):
            raise BusinessRuleError(
                "Cannot complete a parent while active children remain",
                code=errors.INCOMPLETE_CHILDREN,
            )
    completed_at = datetime.now(timezone.utc) if target == TaskStatus.COMPLETED else None
    result = await db.execute(
        update(Task)
        .where(
            Task.tenant_id == tenant_id,
            Task.task_id == task_id,
            Task.version == payload.version,
        )
        .values(
            status=target,
            completed_at=completed_at,
            version=Task.version + 1,
            updated_at=func.now(),
        )
        .returning(Task)
    )
    if result.scalar_one_or_none() is None:
        raise ConflictError("Task was modified by someone else — refresh and retry")
    record_activity(
        db,
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=ActivityEventType.TRANSITIONED,
        actor_user_id=actor_id,
        data={"from_status": old_status, "to_status": target, "reason": payload.reason},
    )
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="task",
        entity_id=task_id,
        action="TRANSITION",
        changed_by_user_id=actor_id,
        old_value={"status": old_status},
        new_value={"status": target, "reason": payload.reason},
    )
    await db.commit()
    read_model = await repository.get_task_read_model(db, tenant_id, task_id)
    if read_model is None:
        raise RuntimeError("Task could not be reloaded after transition")
    return read_model


async def set_task_archived(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    *,
    version: int,
    archived: bool,
) -> repository.TaskReadModel:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    task = await get_task_or_404(db, principal, task_id)
    project = await get_project_or_404(db, principal, task.project_id)
    await assert_can_manage_project(db, principal, task.project_id)
    if project.archived_at is not None:
        raise BusinessRuleError("Restore the project before changing its tasks", code="PROJECT_ARCHIVED")
    archived_at = datetime.now(timezone.utc) if archived else None
    previous_archived_at = task.archived_at
    result = await db.execute(
        update(Task)
        .where(Task.tenant_id == tenant_id, Task.task_id == task_id, Task.version == version)
        .values(archived_at=archived_at, version=Task.version + 1, updated_at=func.now())
        .returning(Task)
    )
    if result.scalar_one_or_none() is None:
        raise ConflictError("Task was modified by someone else — refresh and retry")
    record_activity(
        db,
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=ActivityEventType.ARCHIVED if archived else ActivityEventType.RESTORED,
        actor_user_id=actor_id,
    )
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="task",
        entity_id=task_id,
        action="ARCHIVE" if archived else "RESTORE",
        changed_by_user_id=actor_id,
        old_value={
            "archived_at": previous_archived_at.isoformat() if previous_archived_at else None
        },
        new_value={"archived_at": archived_at.isoformat() if archived_at else None},
    )
    await db.commit()
    read_model = await repository.get_task_read_model(db, tenant_id, task_id)
    if read_model is None:
        raise RuntimeError("Task could not be reloaded after archive operation")
    return read_model


async def add_link(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    payload: TaskLinkCreateRequest,
) -> TaskLink:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    source = await get_task_or_404(db, principal, task_id)
    await assert_task_is_mutable(db, principal, source)
    await assert_can_manage_project(db, principal, source.project_id)
    target = await repository.get_task(db, tenant_id, payload.target_task_id)
    if target is None or target.project_id != source.project_id:
        raise BusinessRuleError("Linked tasks must belong to the same project", code=errors.TASK_LINK_CYCLE)
    if target.archived_at is not None:
        raise BusinessRuleError("Cannot link an archived task", code="TASK_ARCHIVED")
    if source.task_id == target.task_id:
        raise BusinessRuleError("A task cannot link to itself", code=errors.TASK_LINK_CYCLE)
    if payload.link_type == TaskLinkType.BLOCKS and await repository.would_create_block_cycle(
        db, tenant_id, source.task_id, target.task_id
    ):
        raise BusinessRuleError("Blocking dependency would create a cycle", code=errors.TASK_LINK_CYCLE)
    link = TaskLink(
        tenant_id=tenant_id,
        source_task_id=source.task_id,
        target_task_id=target.task_id,
        link_type=payload.link_type,
        created_by_user_id=actor_id,
    )
    db.add(link)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("This task link already exists", code="TASK_LINK_EXISTS") from exc
    record_activity(
        db,
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=ActivityEventType.LINK_ADDED,
        actor_user_id=actor_id,
        data={"target_task_id": str(target.task_id), "link_type": payload.link_type.value},
    )
    await db.commit()
    await db.refresh(link)
    return link


async def list_links(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
) -> PageResponse[TaskLinkResponse]:
    task = await get_task_or_404(db, principal, task_id)
    await assert_can_view_project(db, principal, task.project_id)
    links, total = await repository.list_links(
        db, principal.tenant_id, task_id, page, page_size
    )
    return PageResponse[TaskLinkResponse](
        items=[TaskLinkResponse.model_validate(link) for link in links],
        page=page,
        page_size=page_size,
        total=total,
    )


async def remove_link(
    db: AsyncSession, principal: Principal, task_id: uuid.UUID, link_id: uuid.UUID
) -> None:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    task = await get_task_or_404(db, principal, task_id)
    await assert_task_is_mutable(db, principal, task)
    await assert_can_manage_project(db, principal, task.project_id)
    link = await repository.get_link(db, tenant_id, link_id)
    if link is None or task_id not in {link.source_task_id, link.target_task_id}:
        raise NotFoundError("Task link not found")
    await db.delete(link)
    record_activity(
        db,
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=ActivityEventType.LINK_REMOVED,
        actor_user_id=actor_id,
        data={"link_id": str(link_id)},
    )
    await db.commit()
