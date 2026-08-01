import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.auth.deps import Principal
from app.task_management.models.task_comment import TaskComment
from app.task_management.comments import repository
from app.task_management.tasks import service as task_service
from app.task_management.schemas.comment import CommentCreateRequest


async def create_comment(
    db: AsyncSession, principal: Principal, task_id: uuid.UUID, payload: CommentCreateRequest
) -> TaskComment:
    # Reuses the task module's access check: comments are scoped by project
    # membership at the API layer, same rule as task access — Tenant Admin
    # always, Project Manager on projects they manage, Employee on tasks
    # they're assigned to.
    task = await task_service.get_task_for_principal(db, principal, task_id)

    comment = TaskComment(
        tenant_id=principal.tenant_id,
        task_id=task.task_id,
        commented_by_user_id=principal.id,
        comment_text=payload.comment_text,
    )
    db.add(comment)
    await db.flush()

    await record_audit(
        db,
        tenant_id=principal.tenant_id,
        entity_type="task_comment",
        entity_id=comment.comment_id,
        action="CREATE",
        changed_by_user_id=principal.id,
        new_value={"task_id": str(task.task_id), "comment_text": comment.comment_text},
    )
    await db.commit()
    await db.refresh(comment)
    return comment


async def list_comments(db: AsyncSession, principal: Principal, task_id: uuid.UUID) -> list[TaskComment]:
    await task_service.get_task_for_principal(db, principal, task_id)
    return await repository.list_comments_for_task(db, principal.tenant_id, task_id)
