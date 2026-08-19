"""Compatibility service for the legacy /tasks API."""

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal
from app.core.exceptions import BusinessRuleError
from app.modules.task_management.domain.enums import Priority, TaskStatus, TaskType
from app.modules.task_management.tasks import repository as canonical_repository
from app.modules.task_management.tasks import service as canonical_service
from app.modules.task_management.tasks.model import Task
from app.modules.task_management.tasks.schemas import (
    TaskCreateRequest as CanonicalTaskCreateRequest,
    TaskUpdateRequest as CanonicalTaskUpdateRequest,
)
from app.schemas.task import TaskCreateRequest, TaskUpdateRequest


def _status(value: str | None, *, default: TaskStatus = TaskStatus.NEW) -> TaskStatus:
    try:
        return TaskStatus(value) if value is not None else default
    except ValueError as exc:
        raise BusinessRuleError("Invalid task status", code="TASK_STATUS_INVALID") from exc


def _priority(value: str | None) -> Priority:
    try:
        return Priority(value) if value is not None else Priority.MEDIUM
    except ValueError as exc:
        raise BusinessRuleError("Invalid task priority", code="TASK_PRIORITY_INVALID") from exc


def _attach_actual_hours(read_model: canonical_repository.TaskReadModel) -> Task:
    setattr(read_model.task, "_legacy_actual_hours", read_model.actual_hours)
    return read_model.task


async def create_task(
    db: AsyncSession, principal: Principal, payload: TaskCreateRequest
) -> Task:
    canonical = CanonicalTaskCreateRequest(
        parent_task_id=payload.parent_task_id,
        task_type=TaskType.SUBTASK if payload.parent_task_id else TaskType.TASK,
        name=payload.name,
        description=payload.description,
        task_category=payload.task_category,
        assignee_id=payload.assignee_id,
        technical_lead_id=payload.technical_lead_id,
        functional_lead_id=payload.functional_lead_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        estimated_hours=payload.estimated_hours,
        priority=_priority(payload.priority),
        status=_status(payload.status),
        blocked_by_id=payload.blocked_by_id,
        remarks=payload.remarks,
    )
    return _attach_actual_hours(
        await canonical_service.create_task(
            db,
            principal,
            payload.project_id,
            canonical,
            legacy_attachment_url=payload.attachment_url,
        )
    )


async def get_task_or_404(
    db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID
) -> Task:
    task = await canonical_repository.get_task(db, tenant_id, task_id)
    if task is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Task not found")
    return task


async def get_task_for_principal(
    db: AsyncSession, principal: Principal, task_id: uuid.UUID
) -> Task:
    return _attach_actual_hours(
        await canonical_service.get_task_for_principal(db, principal, task_id)
    )


async def get_actual_hours(
    db: AsyncSession, tenant_id: uuid.UUID, task_id: uuid.UUID
) -> Decimal:
    read_model = await canonical_repository.get_task_read_model(db, tenant_id, task_id)
    return read_model.actual_hours if read_model is not None else Decimal("0")


async def list_tasks(
    db: AsyncSession, principal: Principal, project_id: uuid.UUID | None = None
) -> list[Task]:
    return [
        _attach_actual_hours(item)
        for item in await canonical_service.list_tasks_legacy(db, principal, project_id)
    ]


async def update_task(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    payload: TaskUpdateRequest,
) -> Task:
    values = payload.model_dump(
        exclude={"version", "status", "attachment_url"}, exclude_unset=True
    )
    if "priority" in values and values["priority"] is not None:
        values["priority"] = _priority(values["priority"])
    canonical = CanonicalTaskUpdateRequest.model_validate(
        {**values, "version": payload.version}
    )
    legacy_status = (
        _status(payload.status)
        if "status" in payload.model_fields_set and payload.status is not None
        else None
    )
    return _attach_actual_hours(
        await canonical_service.update_task(
            db,
            principal,
            task_id,
            canonical,
            legacy_status=legacy_status,
            legacy_attachment_url_provided="attachment_url" in payload.model_fields_set,
            legacy_attachment_url=payload.attachment_url,
        )
    )
