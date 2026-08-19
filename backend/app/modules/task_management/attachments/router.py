import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal, get_current_principal
from app.db.session import get_db
from app.modules.task_management.attachments import service
from app.modules.task_management.attachments.schemas import AttachmentResponse
from app.modules.task_management.schemas import PageResponse


router = APIRouter(prefix="/tasks/{task_id}/attachments", tags=["task-management-attachments"])


@router.post("", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    task_id: uuid.UUID,
    file: UploadFile = File(...),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> AttachmentResponse:
    return AttachmentResponse.model_validate(
        await service.upload_attachment(db, principal, task_id, file)
    )


@router.get("", response_model=PageResponse[AttachmentResponse])
async def list_attachments(
    task_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> PageResponse[AttachmentResponse]:
    return await service.list_attachments(
        db, principal, task_id, page=page, page_size=page_size
    )


@router.get("/{attachment_id}/download", response_class=FileResponse)
async def download_attachment(
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    attachment, path = await service.get_attachment_for_download(
        db, principal, task_id, attachment_id
    )
    return FileResponse(
        path,
        media_type=attachment.media_type,
        filename=attachment.original_filename,
        content_disposition_type="attachment",
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> None:
    await service.delete_attachment(db, principal, task_id, attachment_id)
