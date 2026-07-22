import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DailyLogCreateRequest(BaseModel):
    hours_worked: Decimal = Field(gt=0)
    progress_notes: str | None = None
    attachment_url: str | None = None


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
