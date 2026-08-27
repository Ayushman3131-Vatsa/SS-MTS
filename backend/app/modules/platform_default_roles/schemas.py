import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.access_control.shared.catalog import role_code
from app.access_control.shared.enums import AccessLevel
from app.access_control.shared.schemas import PageAccessResponse, PageResponse
from app.common.schemas.base import StrictRequestModel


class DefaultRolePageAccessUpdate(BaseModel):
    page_id: uuid.UUID
    access_level: AccessLevel


class DefaultRoleCreateRequest(StrictRequestModel):
    role_name: str = Field(min_length=1, max_length=255)
    role_code: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    offering_id: uuid.UUID | None = None
    is_system: bool = False
    is_active: bool = True
    entries: list[DefaultRolePageAccessUpdate] = Field(default_factory=list, max_length=250)

    @field_validator("role_name")
    @classmethod
    def normalize_role_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("role_code")
    @classmethod
    def normalize_role_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return role_code(value)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class DefaultRoleUpdateRequest(StrictRequestModel):
    role_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None
    version: int = Field(ge=1)
    entries: list[DefaultRolePageAccessUpdate] | None = Field(default=None, max_length=250)

    @field_validator("role_name")
    @classmethod
    def normalize_role_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def require_changes(self) -> "DefaultRoleUpdateRequest":
        if (
            self.role_name is None
            and self.description is None
            and self.is_active is None
            and self.entries is None
        ):
            raise ValueError("Provide at least one field to update")
        return self


class DefaultRoleListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role_id: uuid.UUID
    role_code: str
    role_name: str
    description: str | None
    offering_id: uuid.UUID | None
    offering_code: str | None
    offering_name: str | None
    module_scope: str
    is_system: bool
    is_active: bool
    page_count: int
    modify_count: int
    view_count: int
    none_count: int
    version: int
    created_at: datetime
    updated_at: datetime


class DefaultRoleDetailResponse(DefaultRoleListItem):
    page_access: list[PageAccessResponse]


class DefaultRolePagesResponse(BaseModel):
    module_scope: str
    offering_id: uuid.UUID | None = None
    offering_code: str | None = None
    offering_name: str | None = None
    pages: list[PageResponse]
