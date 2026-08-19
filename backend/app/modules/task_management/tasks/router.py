import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal, get_current_principal
from app.db.session import get_db
from app.modules.task_management.domain.enums import Priority, TaskStatus, TaskType
from app.modules.task_management.schemas import PageResponse
from app.modules.task_management.tasks import service
from app.modules.task_management.tasks.schemas import (
    TaskArchiveRequest,
    TaskCreateRequest,
    TaskLinkCreateRequest,
    TaskLinkResponse,
    TaskResponse,
    TaskTransitionRequest,
    TaskUpdateRequest,
)


router = APIRouter(tags=["task-management-tasks"])


@router.post(
    "/projects/{project_id}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    project_id: uuid.UUID,
    payload: TaskCreateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    return service.to_response(await service.create_task(db, principal, project_id, payload))


@router.get("/tasks", response_model=PageResponse[TaskResponse])
async def list_tasks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    project_id: uuid.UUID | None = None,
    query: str | None = Query(default=None, max_length=255),
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    priority: Priority | None = None,
    task_type: TaskType | None = None,
    assignee_id: uuid.UUID | None = None,
    reporter_id: uuid.UUID | None = None,
    member_id: uuid.UUID | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    archived: bool | None = None,
    include_archived: bool = False,
    sort: str = Query(
        default="-updated_at",
        pattern=r"^-?(task_number|name|created_at|updated_at|due_date|status|priority)$",
    ),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> PageResponse[TaskResponse]:
    return await service.list_tasks(
        db,
        principal,
        page=page,
        page_size=page_size,
        project_id=project_id,
        query=query,
        status=task_status.value if task_status else None,
        priority=priority.value if priority else None,
        task_type=task_type.value if task_type else None,
        assignee_id=assignee_id,
        reporter_id=reporter_id,
        member_id=member_id,
        due_from=due_from,
        due_to=due_to,
        archived=archived,
        include_archived=include_archived,
        sort=sort,
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    return service.to_response(await service.get_task_for_principal(db, principal, task_id))


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    return service.to_response(await service.update_task(db, principal, task_id, payload))


@router.post("/tasks/{task_id}/transitions", response_model=TaskResponse)
async def transition_task(
    task_id: uuid.UUID,
    payload: TaskTransitionRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    return service.to_response(await service.transition_task(db, principal, task_id, payload))


@router.post("/tasks/{task_id}/archive", response_model=TaskResponse)
async def archive_task(
    task_id: uuid.UUID,
    payload: TaskArchiveRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    return service.to_response(
        await service.set_task_archived(
            db, principal, task_id, version=payload.version, archived=True
        )
    )


@router.post("/tasks/{task_id}/restore", response_model=TaskResponse)
async def restore_task(
    task_id: uuid.UUID,
    payload: TaskArchiveRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    return service.to_response(
        await service.set_task_archived(
            db, principal, task_id, version=payload.version, archived=False
        )
    )


@router.get(
    "/tasks/{task_id}/links", response_model=PageResponse[TaskLinkResponse]
)
async def list_task_links(
    task_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> PageResponse[TaskLinkResponse]:
    return await service.list_links(
        db, principal, task_id, page=page, page_size=page_size
    )


@router.post(
    "/tasks/{task_id}/links",
    response_model=TaskLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_task_link(
    task_id: uuid.UUID,
    payload: TaskLinkCreateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TaskLinkResponse:
    return TaskLinkResponse.model_validate(
        await service.add_link(db, principal, task_id, payload)
    )


@router.delete("/tasks/{task_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_task_link(
    task_id: uuid.UUID,
    link_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.remove_link(db, principal, task_id, link_id)
