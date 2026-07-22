import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.common.deps import Principal
from app.core.exceptions import ForbiddenError
from app.models.daily_progress_log import DailyProgressLog
from app.modules.daily_logs import repository
from app.modules.tasks import service as task_service
from app.schemas.daily_log import DailyLogCreateRequest


async def create_log(
    db: AsyncSession, principal: Principal, task_id: uuid.UUID, payload: DailyLogCreateRequest
) -> DailyProgressLog:
    task = await task_service.get_task_for_principal(db, principal, task_id)

    if principal.role == "Employee" and task.assignee_id != principal.id:
        raise ForbiddenError("Only the assigned Employee may log hours against this task")

    log = DailyProgressLog(
        tenant_id=principal.tenant_id,
        task_id=task.task_id,
        updated_by_user_id=principal.id,
        hours_worked=payload.hours_worked,
        progress_notes=payload.progress_notes,
        attachment_url=payload.attachment_url,
    )
    db.add(log)
    await db.flush()

    await record_audit(
        db,
        tenant_id=principal.tenant_id,
        entity_type="daily_progress_log",
        entity_id=log.log_id,
        action="CREATE",
        changed_by_user_id=principal.id,
        new_value={"task_id": str(task.task_id), "hours_worked": str(payload.hours_worked)},
    )
    await db.commit()
    await db.refresh(log)
    return log


async def list_logs(db: AsyncSession, principal: Principal, task_id: uuid.UUID) -> list[DailyProgressLog]:
    await task_service.get_task_for_principal(db, principal, task_id)
    return await repository.list_logs_for_task(db, principal.tenant_id, task_id)
