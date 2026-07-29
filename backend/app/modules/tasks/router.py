import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal, require_tenant_user
from app.db.session import get_db
from app.modules.tasks import service
from app.schemas.task import TaskCreateRequest, TaskResponse, TaskUpdateRequest

router = APIRouter(prefix="/tasks", tags=["tasks"])


async def _to_response(db: AsyncSession, task) -> TaskResponse:
    actual_hours = await service.get_actual_hours(db, task.tenant_id, task.task_id)
    return TaskResponse.model_validate(task).model_copy(update={"actual_hours": actual_hours})


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreateRequest,
    principal: Principal = Depends(require_tenant_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    task = await service.create_task(db, principal, payload)
    return await _to_response(db, task)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    project_id: uuid.UUID | None = Query(default=None),
    principal: Principal = Depends(require_tenant_user),
    db: AsyncSession = Depends(get_db),
) -> list[TaskResponse]:
    tasks = await service.list_tasks(db, principal, project_id)
    return [await _to_response(db, t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    principal: Principal = Depends(require_tenant_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    task = await service.get_task_for_principal(db, principal, task_id)
    return await _to_response(db, task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdateRequest,
    principal: Principal = Depends(require_tenant_user),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    task = await service.update_task(db, principal, task_id, payload)
    return await _to_response(db, task)
