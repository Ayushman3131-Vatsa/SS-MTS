import uuid
from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.common.schemas.base import StrictRequestModel

ProjectStatus = Literal["Not Started", "In Progress", "Completed", "On Hold", "Cancelled"]
ProjectPriority = Literal["Low", "Medium", "High", "Critical"]


class ProjectCreateRequest(StrictRequestModel):
    name: str = Field(min_length=1, max_length=255)
    client_name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=50_000)
    start_date: date | None = None
    expected_end_date: date | None = None
    status: ProjectStatus | None = "Not Started"
    priority: ProjectPriority | None = None
    pm_id: uuid.UUID | None = None
    dm_id: uuid.UUID | None = None
    remarks: str | None = Field(default=None, max_length=20_000)

    @model_validator(mode="after")
    def validate_dates(self) -> Self:
        if self.start_date and self.expected_end_date and self.expected_end_date < self.start_date:
            raise ValueError("expected_end_date must be on or after start_date")
        return self


class ProjectUpdateRequest(StrictRequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    client_name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=50_000)
    start_date: date | None = None
    expected_end_date: date | None = None
    status: ProjectStatus | None = None
    priority: ProjectPriority | None = None
    pm_id: uuid.UUID | None = None
    dm_id: uuid.UUID | None = None
    remarks: str | None = Field(default=None, max_length=20_000)
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_required_values(self) -> Self:
        for field in ("name", "status", "priority"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        if self.start_date and self.expected_end_date and self.expected_end_date < self.start_date:
            raise ValueError("expected_end_date must be on or after start_date")
        return self


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
