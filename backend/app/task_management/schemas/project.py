import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.common.schemas.base import StrictRequestModel

ProjectStatus = str  # 'Not Started' | 'In Progress' | 'Completed' | 'On Hold' | 'Cancelled'


class ProjectCreateRequest(StrictRequestModel):
    name: str = Field(min_length=1, max_length=255)
    client_name: str | None = None
    description: str | None = None
    start_date: date | None = None
    expected_end_date: date | None = None
    status: ProjectStatus | None = "Not Started"
    priority: str | None = None
    pm_id: uuid.UUID | None = None
    dm_id: uuid.UUID | None = None
    remarks: str | None = None


class ProjectUpdateRequest(StrictRequestModel):
    name: str | None = None
    client_name: str | None = None
    description: str | None = None
    start_date: date | None = None
    expected_end_date: date | None = None
    status: ProjectStatus | None = None
    priority: str | None = None
    pm_id: uuid.UUID | None = None
    dm_id: uuid.UUID | None = None
    remarks: str | None = None
    version: int


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    project_id: uuid.UUID
    name: str
    client_name: str | None
    description: str | None
    start_date: date | None
    expected_end_date: date | None
    status: str | None
    priority: str | None
    pm_id: uuid.UUID | None
    dm_id: uuid.UUID | None
    remarks: str | None
    version: int
