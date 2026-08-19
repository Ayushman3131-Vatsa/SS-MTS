import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal, get_current_principal
from app.db.session import get_db
from app.modules.task_management.activity import service
from app.modules.task_management.activity.schemas import ActivityResponse
from app.modules.task_management.schemas import PageResponse


router = APIRouter(prefix="/tasks/{task_id}/activity", tags=["task-management-activity"])


@router.get("", response_model=PageResponse[ActivityResponse])
async def list_activity(
    task_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> PageResponse[ActivityResponse]:
    return await service.list_activity(
        db, principal, task_id, page=page, page_size=page_size
    )

