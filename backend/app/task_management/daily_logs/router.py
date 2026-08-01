import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import Principal, require_tenant_user
from app.common.db.session import get_db
from app.task_management.daily_logs import service
from app.task_management.schemas.daily_log import DailyLogCreateRequest, DailyLogResponse

router = APIRouter(prefix="/tasks/{task_id}/logs", tags=["daily-logs"])


@router.post("", response_model=DailyLogResponse, status_code=status.HTTP_201_CREATED)
async def create_log(
    task_id: uuid.UUID,
    payload: DailyLogCreateRequest,
    principal: Principal = Depends(require_tenant_user),
    db: AsyncSession = Depends(get_db),
) -> DailyLogResponse:
    log = await service.create_log(db, principal, task_id, payload)
    return DailyLogResponse.model_validate(log)


@router.get("", response_model=list[DailyLogResponse])
async def list_logs(
    task_id: uuid.UUID,
    principal: Principal = Depends(require_tenant_user),
    db: AsyncSession = Depends(get_db),
) -> list[DailyLogResponse]:
    logs = await service.list_logs(db, principal, task_id)
    return [DailyLogResponse.model_validate(l) for l in logs]
