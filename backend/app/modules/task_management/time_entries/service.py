import uuid
from datetime import datetime, timezone

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.common.deps import Principal
from app.core.exceptions import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.modules.task_management.access import (
    assert_can_execute_task,
    assert_can_view_project,
    assert_task_is_mutable,
    project_access,
    require_tenant_principal,
)
from app.modules.task_management.activity.service import record_activity
from app.modules.task_management.domain.enums import ActivityEventType
from app.modules.task_management.domain.policies import can_manage_project
from app.modules.task_management.schemas import PageResponse
from app.modules.task_management.tasks import repository as task_repository
from app.modules.task_management.time_entries import repository
from app.modules.task_management.time_entries.model import DailyProgressLog
from app.modules.task_management.time_entries.schemas import (
    TimeEntryCreateRequest,
    TimeEntryResponse,
    TimeEntryUpdateRequest,
)


async def _task_or_404(db: AsyncSession, principal: Principal, task_id: uuid.UUID):
    task = await task_repository.get_task(db, principal.tenant_id, task_id)
    if task is None:
        raise NotFoundError("Task not found")
    return task


async def create_entry(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    payload: TimeEntryCreateRequest,
    *,
    legacy_attachment_url: str | None = None,
) -> DailyProgressLog:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    task = await _task_or_404(db, principal, task_id)
    await assert_task_is_mutable(db, principal, task)
    await assert_can_execute_task(db, principal, task)
    entry = DailyProgressLog(
        tenant_id=tenant_id,
        task_id=task_id,
        updated_by_user_id=actor_id,
        hours_worked=payload.hours_worked,
        work_date=payload.work_date,
        progress_notes=payload.progress_notes,
        attachment_url=legacy_attachment_url,
    )
    db.add(entry)
    await db.flush()
    record_activity(
        db,
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=ActivityEventType.TIME_LOGGED,
        actor_user_id=actor_id,
        data={"entry_id": str(entry.log_id), "hours_worked": str(entry.hours_worked)},
    )
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="daily_progress_log",
        entity_id=entry.log_id,
        action="CREATE",
        changed_by_user_id=actor_id,
        new_value={
            "task_id": str(task_id),
            "hours_worked": str(entry.hours_worked),
            "work_date": entry.work_date.isoformat(),
        },
    )
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_entries(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
) -> PageResponse[TimeEntryResponse]:
    task = await _task_or_404(db, principal, task_id)
    await assert_can_view_project(db, principal, task.project_id)
    items, total = await repository.list_entries(
        db, principal.tenant_id, task_id, page, page_size
    )
    return PageResponse[TimeEntryResponse](
        items=[TimeEntryResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


async def list_entries_legacy(
    db: AsyncSession, principal: Principal, task_id: uuid.UUID
) -> list[DailyProgressLog]:
    task = await _task_or_404(db, principal, task_id)
    await assert_can_view_project(db, principal, task.project_id)
    entries, _ = await repository.list_entries(
        db, principal.tenant_id, task_id, 1, 1_000_000
    )
    return entries


async def _assert_can_edit_entry(db, principal, task, entry) -> None:
    access = await project_access(db, principal, task.project_id)
    if entry.updated_by_user_id != principal.id and not can_manage_project(access):
        raise ForbiddenError("Only the author or a project manager may modify this time entry")


async def update_entry(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    entry_id: uuid.UUID,
    payload: TimeEntryUpdateRequest,
) -> DailyProgressLog:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    task = await _task_or_404(db, principal, task_id)
    await assert_task_is_mutable(db, principal, task)
    await assert_can_view_project(db, principal, task.project_id)
    entry = await repository.get_entry(db, tenant_id, entry_id)
    if entry is None or entry.task_id != task_id or entry.deleted_at is not None:
        raise NotFoundError("Time entry not found")
    await _assert_can_edit_entry(db, principal, task, entry)
    values = payload.model_dump(exclude={"version"}, exclude_unset=True, mode="python")
    if not values:
        raise BusinessRuleError("Provide at least one time-entry field to update", code="TIME_ENTRY_UPDATE_EMPTY")
    old_hours = entry.hours_worked
    old_work_date = entry.work_date
    result = await db.execute(
        update(DailyProgressLog)
        .where(
            DailyProgressLog.tenant_id == tenant_id,
            DailyProgressLog.log_id == entry_id,
            DailyProgressLog.version == payload.version,
            DailyProgressLog.deleted_at.is_(None),
        )
        .values(**values, version=DailyProgressLog.version + 1, updated_at=func.now())
        .returning(DailyProgressLog)
    )
    updated = result.scalar_one_or_none()
    if updated is None:
        raise ConflictError("Time entry was modified by someone else — refresh and retry")
    record_activity(
        db,
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=ActivityEventType.TIME_UPDATED,
        actor_user_id=actor_id,
        data={"entry_id": str(entry_id)},
    )
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="daily_progress_log",
        entity_id=entry_id,
        action="UPDATE",
        changed_by_user_id=actor_id,
        old_value={"hours_worked": str(old_hours), "work_date": old_work_date.isoformat()},
        new_value=payload.model_dump(exclude={"version"}, exclude_unset=True, mode="json"),
    )
    await db.commit()
    await db.refresh(updated)
    return updated


async def delete_entry(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    entry_id: uuid.UUID,
    *,
    version: int,
) -> None:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    task = await _task_or_404(db, principal, task_id)
    await assert_task_is_mutable(db, principal, task)
    await assert_can_view_project(db, principal, task.project_id)
    entry = await repository.get_entry(db, tenant_id, entry_id)
    if entry is None or entry.task_id != task_id or entry.deleted_at is not None:
        raise NotFoundError("Time entry not found")
    await _assert_can_edit_entry(db, principal, task, entry)
    old_hours = entry.hours_worked
    result = await db.execute(
        update(DailyProgressLog)
        .where(
            DailyProgressLog.tenant_id == tenant_id,
            DailyProgressLog.log_id == entry_id,
            DailyProgressLog.version == version,
            DailyProgressLog.deleted_at.is_(None),
        )
        .values(
            deleted_at=datetime.now(timezone.utc),
            version=DailyProgressLog.version + 1,
            updated_at=func.now(),
        )
    )
    if not result.rowcount:
        raise ConflictError("Time entry was modified by someone else — refresh and retry")
    record_activity(
        db,
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=ActivityEventType.TIME_DELETED,
        actor_user_id=actor_id,
        data={"entry_id": str(entry_id)},
    )
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="daily_progress_log",
        entity_id=entry_id,
        action="DELETE",
        changed_by_user_id=actor_id,
        old_value={"hours_worked": str(old_hours)},
        new_value={"deleted": True},
    )
    await db.commit()
