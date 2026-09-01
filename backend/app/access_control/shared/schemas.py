import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.access_control.shared.enums import AccessLevel
from app.common.schemas.base import StrictRequestModel


class RoleCreateRequest(StrictRequestModel):
    role_name: str = Field(min_length=1, max_length=255)
    role_code: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    module_scope: str | None = Field(default=None, min_length=1, max_length=100)

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
        normalized = value.strip().upper().replace(" ", "_")
        return normalized or None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("module_scope")
    @classmethod
    def normalize_module_scope(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RoleUpdateRequest(StrictRequestModel):
    role_name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)

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


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role_id: uuid.UUID
    role_code: str
    role_name: str
    description: str | None
    is_system: bool
    is_active: bool
    module_scope: str | None = None
    users_count: int = 0
    created_at: datetime


class PageResponse(BaseModel):
    page_id: uuid.UUID
    page_code: str
    module: str
    page_name: str
    route: str
    app_scope: str
    offering_code: str | None = None


class PageAccessResponse(BaseModel):
    page: PageResponse
    access_level: AccessLevel


class PageAccessUpdate(BaseModel):
    page_id: uuid.UUID
    access_level: AccessLevel


class PageAccessUpdateRequest(StrictRequestModel):
    entries: list[PageAccessUpdate] = Field(default_factory=list, max_length=250)


class SessionPageAccess(BaseModel):
    page_code: str
    module: str
    page_name: str
    route: str
    access_level: AccessLevel
    offering_code: str | None = None


Realm = Literal["platform", "tenant"]
