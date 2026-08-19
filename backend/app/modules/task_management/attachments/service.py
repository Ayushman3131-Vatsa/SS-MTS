import re
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.common.deps import Principal
from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError, ForbiddenError, NotFoundError
from app.modules.task_management.access import (
    assert_can_comment_or_attach,
    assert_can_view_project,
    assert_task_is_mutable,
    project_access,
    require_tenant_principal,
)
from app.modules.task_management.activity.service import record_activity
from app.modules.task_management.attachments import repository
from app.modules.task_management.attachments.local_storage import LocalAttachmentStorage
from app.modules.task_management.attachments.model import TaskAttachment
from app.modules.task_management.attachments.schemas import AttachmentResponse
from app.modules.task_management.domain import errors
from app.modules.task_management.domain.enums import ActivityEventType
from app.modules.task_management.domain.policies import can_manage_project
from app.modules.task_management.schemas import PageResponse
from app.modules.task_management.tasks import repository as task_repository


@lru_cache
def get_attachment_storage() -> LocalAttachmentStorage:
    return LocalAttachmentStorage(get_settings().attachment_storage_root)


def _safe_filename(filename: str | None) -> str:
    # Browsers may submit either POSIX or Windows separators regardless of the
    # application host OS. The name is metadata only and is never a disk path.
    name = re.split(r"[\\/]", filename or "attachment")[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    if not name:
        name = "attachment"
    return name[:255]


async def _task_or_404(db: AsyncSession, principal: Principal, task_id: uuid.UUID):
    task = await task_repository.get_task(db, principal.tenant_id, task_id)
    if task is None:
        raise NotFoundError("Task not found")
    return task


async def upload_attachment(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    upload: UploadFile,
) -> TaskAttachment:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    task = await _task_or_404(db, principal, task_id)
    await assert_task_is_mutable(db, principal, task)
    await assert_can_comment_or_attach(db, principal, task.project_id)
    settings = get_settings()
    allowed = {value.strip().lower() for value in settings.attachment_allowed_media_types.split(",") if value.strip()}
    media_type = (upload.content_type or "application/octet-stream").lower()
    if media_type not in allowed:
        await upload.close()
        raise BusinessRuleError("Attachment media type is not allowed", code=errors.ATTACHMENT_TYPE)
    if await repository.count_active_attachments(db, tenant_id, task_id) >= settings.attachment_max_per_task:
        await upload.close()
        raise BusinessRuleError(
            f"A task may have at most {settings.attachment_max_per_task} active attachments",
            code=errors.ATTACHMENT_LIMIT,
        )

    storage_key = f"{uuid.uuid4().hex[:2]}/{uuid.uuid4().hex}"
    storage = get_attachment_storage()
    try:
        size = await storage.save(storage_key, upload, max_bytes=settings.attachment_max_bytes)
        attachment = TaskAttachment(
            tenant_id=tenant_id,
            task_id=task_id,
            storage_key=storage_key,
            original_filename=_safe_filename(upload.filename),
            media_type=media_type,
            size_bytes=size,
            uploaded_by_user_id=actor_id,
        )
        db.add(attachment)
        await db.flush()
        record_activity(
            db,
            tenant_id=tenant_id,
            task_id=task_id,
            event_type=ActivityEventType.ATTACHMENT_ADDED,
            actor_user_id=actor_id,
            data={"attachment_id": str(attachment.attachment_id), "filename": attachment.original_filename},
        )
        await record_audit(
            db,
            tenant_id=tenant_id,
            entity_type="task_attachment",
            entity_id=attachment.attachment_id,
            action="CREATE",
            changed_by_user_id=actor_id,
            new_value={
                "task_id": str(task_id),
                "filename": attachment.original_filename,
                "media_type": media_type,
                "size_bytes": size,
            },
        )
        await db.commit()
        await db.refresh(attachment)
        return attachment
    except Exception:
        await db.rollback()
        await storage.delete(storage_key)
        raise


async def list_attachments(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
) -> PageResponse[AttachmentResponse]:
    task = await _task_or_404(db, principal, task_id)
    await assert_can_view_project(db, principal, task.project_id)
    attachments, total = await repository.list_attachments(
        db, principal.tenant_id, task_id, page, page_size
    )
    return PageResponse[AttachmentResponse](
        items=[AttachmentResponse.model_validate(item) for item in attachments],
        page=page,
        page_size=page_size,
        total=total,
    )


async def get_attachment_for_download(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> tuple[TaskAttachment, Path]:
    task = await _task_or_404(db, principal, task_id)
    await assert_can_view_project(db, principal, task.project_id)
    attachment = await repository.get_attachment(db, principal.tenant_id, attachment_id)
    if attachment is None or attachment.task_id != task_id or attachment.deleted_at is not None:
        raise NotFoundError("Attachment not found")
    path = get_attachment_storage().resolve(attachment.storage_key)
    if not path.is_file():
        raise NotFoundError("Attachment content is unavailable")
    return attachment, path


async def delete_attachment(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> None:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    task = await _task_or_404(db, principal, task_id)
    await assert_task_is_mutable(db, principal, task)
    await assert_can_view_project(db, principal, task.project_id)
    attachment = await repository.get_attachment(db, tenant_id, attachment_id)
    if attachment is None or attachment.task_id != task_id or attachment.deleted_at is not None:
        raise NotFoundError("Attachment not found")
    access = await project_access(db, principal, task.project_id)
    if attachment.uploaded_by_user_id != actor_id and not can_manage_project(access):
        raise ForbiddenError("Only the uploader or a project manager may delete this attachment")
    attachment.deleted_at = datetime.now(timezone.utc)
    record_activity(
        db,
        tenant_id=tenant_id,
        task_id=task_id,
        event_type=ActivityEventType.ATTACHMENT_DELETED,
        actor_user_id=actor_id,
        data={"attachment_id": str(attachment_id)},
    )
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="task_attachment",
        entity_id=attachment_id,
        action="DELETE",
        changed_by_user_id=actor_id,
        old_value={"filename": attachment.original_filename, "size_bytes": attachment.size_bytes},
        new_value={"deleted": True},
    )
    await db.commit()
    try:
        await get_attachment_storage().delete(attachment.storage_key)
    except OSError:
        # The metadata is already inaccessible. A storage sweeper can remove
        # an orphan without making the successful API deletion appear failed.
        pass
