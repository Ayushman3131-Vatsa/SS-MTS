import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.access_control.shared.schemas import RoleResponse
from app.auth.username_identity import parse_username
from app.common.schemas.base import StrictRequestModel
from app.common.security import normalize_email, validate_password


class PlatformUserCreateRequest(StrictRequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = Field(default=None, max_length=254)
    username: str = Field(min_length=3, max_length=50)
    employee_id: str | None = Field(default=None, max_length=50)
    password: str | None = Field(default=None, min_length=1, max_length=128)
    role_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)

    @field_validator("name", "first_name", "last_name")
    @classmethod
    def normalize_name_parts(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("employee_id", mode="before")
    @classmethod
    def normalize_employee_id(cls, value: object) -> object:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("email", mode="before")
    @classmethod
    def normalize_platform_email(cls, value: object) -> object:
        return normalize_email(value) if isinstance(value, str) else value

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return parse_username(value)

    @model_validator(mode="after")
    def enforce_password_policy(self) -> "PlatformUserCreateRequest":
        display_name = self.name
        if not display_name:
            parts = [part for part in (self.first_name, self.last_name) if part]
            display_name = " ".join(parts) or None
        if not display_name:
            display_name = self.username
        object.__setattr__(self, "name", display_name)
        # Email is optional for sign-in (username works), but the DB column is NOT NULL
        # with a unique constraint — store an internal placeholder when none is provided.
        email = str(self.email).strip() if self.email else f"{self.username}@accounts.local"
        object.__setattr__(self, "email", normalize_email(email))
        if self.password:
            validate_password(self.password, email=email, name=display_name, username=self.username)
        return self


class PlatformUserUpdateRequest(StrictRequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    username: str | None = Field(default=None, min_length=3, max_length=50)
    employee_id: str | None = Field(default=None, max_length=50)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("username")
    @classmethod
    def normalize_optional_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return parse_username(value)

    @field_validator("employee_id", mode="before")
    @classmethod
    def normalize_employee_id(cls, value: object) -> object:
        if value is None or value == "":
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class PlatformUserResponse(BaseModel):
    admin_id: uuid.UUID
    name: str
    username: str
    email: str
    employee_id: str | None = None
    roles: list[RoleResponse]
    is_active: bool = True
    failed_login_count: int
    locked_until: datetime | None
    last_login_at: datetime | None
    created_at: datetime
    temporary_password: str | None = None


class PlatformUserRoleAssignmentRequest(StrictRequestModel):
    role_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
