import uuid
from datetime import datetime, timezone

from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.common.deps import Principal
from app.core.exceptions import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.modules.task_management.access import (
    assert_can_comment_or_attach,
    assert_can_view_project,
    assert_task_is_mutable,
    project_access,
    require_tenant_principal,
)
from app.modules.task_management.activity.service import record_activity
from app.modules.task_management.comments import repository
from app.modules.task_management.comments.model import TaskComment
from app.modules.task_management.comments.schemas import (
    CommentCreateRequest,
    CommentResponse,
    CommentUpdateRequest,
)
from app.modules.task_management.domain.enums import ActivityEventType
from app.modules.task_management.domain.policies import can_manage_project
from app.modules.task_management.schemas import PageResponse
from app.modules.task_management.tasks import repository as task_repository


async def _task_or_404(db: AsyncSession, principal: Principal, task_id: uuid.UUID):
    task = await task_repository.get_task(db, principal.tenant_id, task_id)
    if task is None:
        raise NotFoundError("Task not found")
    return task


async def create_comment(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    payload: CommentCreateRequest,
) -> TaskComment:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    task = await _task_or_404(db, principal, task_id)
    await assert_task_is_mutable(db, principal, task)
    await assert_can_comment_or_attach(db, principal, task.project_id)
    text = payload.comment_text.strip()
    if not text:
        raise BusinessRuleError("Comment must not be blank", code="COMMENT_BLANK")
    comment = TaskComment(
        tenant_id=tenant_id,
        task_id=task_id,
        commented_by_user_id=actor_id,
        comment_text=text,
    )
    db.add(comment)
    await db.flush()
    record_activity(
        db,
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=ActivityEventType.COMMENTED,
        actor_user_id=actor_id,
        data={"comment_id": str(comment.comment_id)},
    )
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="task_comment",
        entity_id=comment.comment_id,
        action="CREATE",
        changed_by_user_id=actor_id,
        new_value={"task_id": str(task_id), "comment_text": text},
    )
    await db.commit()
    await db.refresh(comment)
    return comment


async def list_comments(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
) -> PageResponse[CommentResponse]:
    task = await _task_or_404(db, principal, task_id)
    await assert_can_view_project(db, principal, task.project_id)
    comments, total = await repository.list_comments(
        db, principal.tenant_id, task_id, page, page_size
    )
    return PageResponse[CommentResponse](
        items=[CommentResponse.model_validate(comment) for comment in comments],
        page=page,
        page_size=page_size,
        total=total,
    )


async def list_comments_legacy(
    db: AsyncSession, principal: Principal, task_id: uuid.UUID
) -> list[TaskComment]:
    task = await _task_or_404(db, principal, task_id)
    await assert_can_view_project(db, principal, task.project_id)
    comments, _ = await repository.list_comments(
        db, principal.tenant_id, task_id, 1, 1_000_000
    )
    return comments


async def _assert_can_moderate(
    db: AsyncSession, principal: Principal, task, comment: TaskComment
) -> None:
    access = await project_access(db, principal, task.project_id)
    if comment.commented_by_user_id != principal.id and not can_manage_project(access):
        raise ForbiddenError("Only the author or a project manager may modify this comment")


async def update_comment(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    payload: CommentUpdateRequest,
) -> TaskComment:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    task = await _task_or_404(db, principal, task_id)
    await assert_task_is_mutable(db, principal, task)
    await assert_can_view_project(db, principal, task.project_id)
    comment = await repository.get_comment(db, tenant_id, comment_id)
    if comment is None or comment.task_id != task_id or comment.deleted_at is not None:
        raise NotFoundError("Comment not found")
    await _assert_can_moderate(db, principal, task, comment)
    text = payload.comment_text.strip()
    if not text:
        raise BusinessRuleError("Comment must not be blank", code="COMMENT_BLANK")
    old_text = comment.comment_text
    result = await db.execute(
        update(TaskComment)
        .where(
            TaskComment.tenant_id == tenant_id,
            TaskComment.comment_id == comment_id,
            TaskComment.version == payload.version,
            TaskComment.deleted_at.is_(None),
        )
        .values(comment_text=text, version=TaskComment.version + 1, updated_at=func.now())
        .returning(TaskComment)
    )
    updated = result.scalar_one_or_none()
    if updated is None:
        raise ConflictError("Comment was modified by someone else — refresh and retry")
    record_activity(
        db,
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=ActivityEventType.COMMENT_UPDATED,
        actor_user_id=actor_id,
        data={"comment_id": str(comment_id)},
    )
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="task_comment",
        entity_id=comment_id,
        action="UPDATE",
        changed_by_user_id=actor_id,
        old_value={"comment_text": old_text},
        new_value={"comment_text": text},
    )
    await db.commit()
    await db.refresh(updated)
    return updated


async def delete_comment(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    *,
    version: int,
) -> None:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    task = await _task_or_404(db, principal, task_id)
    await assert_task_is_mutable(db, principal, task)
    await assert_can_view_project(db, principal, task.project_id)
    comment = await repository.get_comment(db, tenant_id, comment_id)
    if comment is None or comment.task_id != task_id or comment.deleted_at is not None:
        raise NotFoundError("Comment not found")
    await _assert_can_moderate(db, principal, task, comment)
    old_text = comment.comment_text
    result = await db.execute(
        update(TaskComment)
        .where(
            TaskComment.tenant_id == tenant_id,
            TaskComment.comment_id == comment_id,
            TaskComment.version == version,
            TaskComment.deleted_at.is_(None),
        )
        .values(
            comment_text="[deleted]",
            deleted_at=datetime.now(timezone.utc),
            version=TaskComment.version + 1,
            updated_at=func.now(),
        )
    )
    if not result.rowcount:
        raise ConflictError("Comment was modified by someone else — refresh and retry")
    record_activity(
        db,
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=ActivityEventType.COMMENT_DELETED,
        actor_user_id=actor_id,
        data={"comment_id": str(comment_id)},
    )
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="task_comment",
        entity_id=comment_id,
        action="DELETE",
        changed_by_user_id=actor_id,
        old_value={"comment_text": old_text},
        new_value={"deleted": True},
    )
    await db.commit()
