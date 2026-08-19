import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.common.schemas.base import StrictRequestModel


class DailyLogCreateRequest(StrictRequestModel):
    hours_worked: Decimal = Field(gt=0, le=24, max_digits=5, decimal_places=2)
    progress_notes: str | None = Field(default=None, max_length=20_000)
    attachment_url: str | None = Field(default=None, max_length=2000)


class DailyLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    log_id: uuid.UUID
    task_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    hours_worked: Decimal
    progress_notes: str | None
    attachment_url: str | None
    log_date: datetime
