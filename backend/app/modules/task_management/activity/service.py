import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal
from app.modules.task_management.access import assert_can_view_project
from app.modules.task_management.activity import repository
from app.modules.task_management.activity.model import TaskActivityEvent
from app.modules.task_management.activity.schemas import ActivityResponse
from app.modules.task_management.schemas import PageResponse
from app.modules.task_management.tasks import repository as task_repository


def record_activity(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    task_id: uuid.UUID,
    event_type: str,
    actor_user_id: uuid.UUID | None,
    data: dict | None = None,
) -> TaskActivityEvent:
    event = TaskActivityEvent(
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        data=data or {},
    )
    db.add(event)
    return event


async def list_activity(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
) -> PageResponse[ActivityResponse]:
    task = await task_repository.get_task(db, principal.tenant_id, task_id)
    if task is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Task not found")
    await assert_can_view_project(db, principal, task.project_id)
    items, total = await repository.list_activity(
        db, principal.tenant_id, task_id, page, page_size
    )
    return PageResponse[ActivityResponse](
        items=[ActivityResponse.model_validate(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )

