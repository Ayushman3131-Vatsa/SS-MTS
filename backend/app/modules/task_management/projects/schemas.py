import uuid
from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.task_management.domain.enums import Priority, ProjectStatus
from app.schemas.base import StrictRequestModel


PROJECT_KEY_PATTERN = r"^[A-Z][A-Z0-9]{1,9}$"


class ProjectCreateRequest(StrictRequestModel):
    project_key: str | None = Field(default=None, pattern=PROJECT_KEY_PATTERN)
    name: str = Field(min_length=1, max_length=255)
    client_name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=50_000)
    start_date: date | None = None
    expected_end_date: date | None = None
    status: ProjectStatus = ProjectStatus.NOT_STARTED
    priority: Priority = Priority.MEDIUM
    pm_id: uuid.UUID | None = None
    dm_id: uuid.UUID | None = None
    remarks: str | None = Field(default=None, max_length=20_000)

    @field_validator("project_key", mode="before")
    @classmethod
    def normalize_key(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

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
    priority: Priority | None = None
    pm_id: uuid.UUID | None = None
    dm_id: uuid.UUID | None = None
    remarks: str | None = Field(default=None, max_length=20_000)
    version: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def reject_invalid_nulls(self) -> Self:
        required = {"name", "status", "priority"}
        if any(field in self.model_fields_set and getattr(self, field) is None for field in required):
            raise ValueError("name, status and priority cannot be null")
        if self.start_date and self.expected_end_date and self.expected_end_date < self.start_date:
            raise ValueError("expected_end_date must be on or after start_date")
        return self


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    project_id: uuid.UUID
    project_key: str
    name: str
    client_name: str | None
    description: str | None
    start_date: date | None
    expected_end_date: date | None
    status: ProjectStatus
    priority: Priority
    pm_id: uuid.UUID | None
    dm_id: uuid.UUID | None
    remarks: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class ProjectArchiveRequest(StrictRequestModel):
    version: int = Field(ge=1)
