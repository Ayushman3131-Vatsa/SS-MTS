"""Compatibility service for legacy task comments."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import Principal
from app.modules.task_management.comments import service as canonical_service
from app.modules.task_management.comments.model import TaskComment
from app.modules.task_management.comments.schemas import CommentCreateRequest as CanonicalCommentCreateRequest
from app.task_management.schemas.comment import CommentCreateRequest


async def create_comment(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    payload: CommentCreateRequest,
) -> TaskComment:
    return await canonical_service.create_comment(
        db,
        principal,
        task_id,
        CanonicalCommentCreateRequest(comment_text=payload.comment_text),
    )


async def list_comments(
    db: AsyncSession, principal: Principal, task_id: uuid.UUID
) -> list[TaskComment]:
    return await canonical_service.list_comments_legacy(db, principal, task_id)
