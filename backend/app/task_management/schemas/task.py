import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.common.schemas.base import StrictRequestModel

TaskStatus = str  # 'New' | 'Assigned' | 'In Progress' | 'Blocked' | 'On Hold' | 'Under Review' | 'Completed' | 'Cancelled'


class TaskCreateRequest(StrictRequestModel):
    project_id: uuid.UUID
    parent_task_id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    task_category: str | None = None
    assignee_id: uuid.UUID | None = None
    technical_lead_id: uuid.UUID | None = None
    functional_lead_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    estimated_hours: Decimal
    priority: str | None = None
    status: TaskStatus | None = "New"
    blocked_by_id: uuid.UUID | None = None
    remarks: str | None = None
    attachment_url: str | None = None


class TaskUpdateRequest(StrictRequestModel):
    name: str | None = None
    description: str | None = None
    task_category: str | None = None
    assignee_id: uuid.UUID | None = None
    technical_lead_id: uuid.UUID | None = None
    functional_lead_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    estimated_hours: Decimal | None = None
    priority: str | None = None
    status: TaskStatus | None = None
    blocked_by_id: uuid.UUID | None = None
    remarks: str | None = None
    attachment_url: str | None = None
    version: int


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
