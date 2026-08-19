import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal, get_current_principal
from app.db.session import get_db
from app.modules.task_management.schemas import PageResponse
from app.modules.task_management.time_entries import service
from app.modules.task_management.time_entries.schemas import (
    TimeEntryCreateRequest,
    TimeEntryDeleteRequest,
    TimeEntryResponse,
    TimeEntryUpdateRequest,
)


router = APIRouter(prefix="/tasks/{task_id}/time-entries", tags=["task-management-time"])


@router.post("", response_model=TimeEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    task_id: uuid.UUID,
    payload: TimeEntryCreateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TimeEntryResponse:
    return TimeEntryResponse.model_validate(
        await service.create_entry(db, principal, task_id, payload)
    )


@router.get("", response_model=PageResponse[TimeEntryResponse])
async def list_entries(
    task_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> PageResponse[TimeEntryResponse]:
    return await service.list_entries(
        db, principal, task_id, page=page, page_size=page_size
    )


@router.patch("/{entry_id}", response_model=TimeEntryResponse)
async def update_entry(
    task_id: uuid.UUID,
    entry_id: uuid.UUID,
    payload: TimeEntryUpdateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> TimeEntryResponse:
    return TimeEntryResponse.model_validate(
        await service.update_entry(db, principal, task_id, entry_id, payload)
    )


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    task_id: uuid.UUID,
    entry_id: uuid.UUID,
    payload: TimeEntryDeleteRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_entry(db, principal, task_id, entry_id, version=payload.version)

