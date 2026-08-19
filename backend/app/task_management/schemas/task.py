import uuid
from datetime import date
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.common.schemas.base import StrictRequestModel

TaskStatus = Literal[
    "New", "Assigned", "In Progress", "Blocked", "On Hold", "Under Review", "Completed", "Cancelled"
]
TaskPriority = Literal["Low", "Medium", "High", "Critical"]


class TaskCreateRequest(StrictRequestModel):
    project_id: uuid.UUID
    parent_task_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=50_000)
    task_category: str | None = Field(default=None, max_length=100)
    assignee_id: uuid.UUID | None = None
    technical_lead_id: uuid.UUID | None = None
    functional_lead_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    estimated_hours: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    priority: TaskPriority | None = None
    status: TaskStatus | None = "New"
    blocked_by_id: uuid.UUID | None = None
    remarks: str | None = Field(default=None, max_length=20_000)
    attachment_url: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class TaskUpdateRequest(StrictRequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=50_000)
    task_category: str | None = Field(default=None, max_length=100)
    assignee_id: uuid.UUID | None = None
    technical_lead_id: uuid.UUID | None = None
    functional_lead_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    blocked_by_id: uuid.UUID | None = None
    remarks: str | None = Field(default=None, max_length=20_000)
    attachment_url: str | None = Field(default=None, max_length=2000)
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        for field in ("name", "estimated_hours", "priority", "status"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    task_id: uuid.UUID
    project_id: uuid.UUID
    parent_task_id: uuid.UUID | None
    name: str
    description: str | None
    task_category: str | None
    assignee_id: uuid.UUID | None
    technical_lead_id: uuid.UUID | None
    functional_lead_id: uuid.UUID | None
    start_date: date | None
    end_date: date | None
    estimated_hours: Decimal
    priority: str | None
    status: str | None
    blocked_by_id: uuid.UUID | None
    remarks: str | None
    attachment_url: str | None
    version: int
    actual_hours: Decimal = Decimal("0")
