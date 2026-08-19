import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.base import StrictRequestModel


class TimeEntryCreateRequest(StrictRequestModel):
    hours_worked: Decimal = Field(gt=0, le=24, max_digits=5, decimal_places=2)
    work_date: date = Field(default_factory=date.today)
    progress_notes: str | None = Field(default=None, max_length=20_000)


class TimeEntryUpdateRequest(StrictRequestModel):
    hours_worked: Decimal | None = Field(default=None, gt=0, le=24, max_digits=5, decimal_places=2)
    work_date: date | None = None
    progress_notes: str | None = Field(default=None, max_length=20_000)
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def reject_required_nulls(self):
        for field in ("hours_worked", "work_date"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class TimeEntryDeleteRequest(StrictRequestModel):
    version: int = Field(ge=1)


class TimeEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: uuid.UUID
    task_id: uuid.UUID
    updated_by_user_id: uuid.UUID
    hours_worked: Decimal
    work_date: date
    progress_notes: str | None
    version: int
    log_date: datetime
    updated_at: datetime
    deleted_at: datetime | None
