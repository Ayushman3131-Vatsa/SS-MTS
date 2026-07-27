import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal, require_tenant_user
from app.db.session import get_db
from app.modules.comments import service
from app.schemas.comment import CommentCreateRequest, CommentResponse

router = APIRouter(prefix="/tasks/{task_id}/comments", tags=["comments"])


@router.post("", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    task_id: uuid.UUID,
    payload: CommentCreateRequest,
    principal: Principal = Depends(require_tenant_user),
    db: AsyncSession = Depends(get_db),
) -> CommentResponse:
    comment = await service.create_comment(db, principal, task_id, payload)
    return CommentResponse.model_validate(comment)


@router.get("", response_model=list[CommentResponse])
async def list_comments(
    task_id: uuid.UUID,
    principal: Principal = Depends(require_tenant_user),
    db: AsyncSession = Depends(get_db),
) -> list[CommentResponse]:
    comments = await service.list_comments(db, principal, task_id)
    return [CommentResponse.model_validate(c) for c in comments]
