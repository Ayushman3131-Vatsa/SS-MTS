import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.task_management.domain.enums import Priority, TaskLinkType, TaskStatus, TaskType
from app.schemas.base import StrictRequestModel


class TaskCreateRequest(StrictRequestModel):
    parent_task_id: uuid.UUID | None = None
    task_type: TaskType = TaskType.TASK
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=50_000)
    task_category: str | None = Field(default=None, max_length=100)
    assignee_id: uuid.UUID | None = None
    technical_lead_id: uuid.UUID | None = None
    functional_lead_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    estimated_hours: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.NEW
    blocked_by_id: uuid.UUID | None = None
    remarks: str | None = Field(default=None, max_length=20_000)

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name must not be blank")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class TaskUpdateRequest(StrictRequestModel):
    parent_task_id: uuid.UUID | None = None
    task_type: TaskType | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=50_000)
    task_category: str | None = Field(default=None, max_length=100)
    assignee_id: uuid.UUID | None = None
    technical_lead_id: uuid.UUID | None = None
    functional_lead_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    priority: Priority | None = None
    blocked_by_id: uuid.UUID | None = None
    remarks: str | None = Field(default=None, max_length=20_000)
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_values(self) -> Self:
        if "name" in self.model_fields_set:
            if self.name is None:
                raise ValueError("name cannot be null")
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("name must not be blank")
        if "priority" in self.model_fields_set and self.priority is None:
            raise ValueError("priority cannot be null")
        if "task_type" in self.model_fields_set and self.task_type is None:
            raise ValueError("task_type cannot be null")
        if "estimated_hours" in self.model_fields_set and self.estimated_hours is None:
            raise ValueError("estimated_hours cannot be null")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class TaskTransitionRequest(StrictRequestModel):
    to_status: TaskStatus
    version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=1000)


class TaskArchiveRequest(StrictRequestModel):
    version: int = Field(ge=1)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    task_id: uuid.UUID
    project_id: uuid.UUID
    task_number: int
    display_key: str
    task_type: TaskType
    parent_task_id: uuid.UUID | None
    name: str
    description: str | None
    task_category: str | None
    assignee_id: uuid.UUID | None
    technical_lead_id: uuid.UUID | None
    functional_lead_id: uuid.UUID | None
    reporter_id: uuid.UUID | None
    created_by_user_id: uuid.UUID | None
    start_date: date | None
    end_date: date | None
    estimated_hours: Decimal
    actual_hours: Decimal = Decimal("0")
    priority: Priority
    status: TaskStatus
    blocked_by_id: uuid.UUID | None
    remarks: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    archived_at: datetime | None


class TaskLinkCreateRequest(StrictRequestModel):
    target_task_id: uuid.UUID
    link_type: TaskLinkType


class TaskLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    link_id: uuid.UUID
    source_task_id: uuid.UUID
    target_task_id: uuid.UUID
    link_type: TaskLinkType
    created_by_user_id: uuid.UUID
    created_at: datetime
