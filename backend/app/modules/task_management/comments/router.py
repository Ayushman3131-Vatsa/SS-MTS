import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal, get_current_principal
from app.db.session import get_db
from app.modules.task_management.comments import service
from app.modules.task_management.comments.schemas import (
    CommentCreateRequest,
    CommentDeleteRequest,
    CommentResponse,
    CommentUpdateRequest,
)
from app.modules.task_management.schemas import PageResponse


router = APIRouter(prefix="/tasks/{task_id}/comments", tags=["task-management-comments"])


@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    task_id: uuid.UUID,
    payload: CommentCreateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    return CommentResponse.model_validate(
        await service.create_comment(db, principal, task_id, payload)
    )


@router.get("", response_model=PageResponse[CommentResponse])
async def list_comments(
    task_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> PageResponse[CommentResponse]:
    return await service.list_comments(
        db, principal, task_id, page=page, page_size=page_size
    )


@router.patch("/{comment_id}", response_model=CommentResponse)
async def update_comment(
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    payload: CommentUpdateRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    return CommentResponse.model_validate(
        await service.update_comment(db, principal, task_id, comment_id, payload)
    )


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    payload: CommentDeleteRequest,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_comment(
        db, principal, task_id, comment_id, version=payload.version
    )

