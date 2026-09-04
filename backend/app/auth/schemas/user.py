import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.auth.username_identity import parse_username
from app.common.security import normalize_email, validate_password
from app.common.schemas.base import StrictRequestModel


class UserCreateRequest(StrictRequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, min_length=1, max_length=120)
    employee_id: str | None = Field(default=None, max_length=50)
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr | None = Field(default=None, max_length=254)
    password: str | None = Field(default=None, min_length=1, max_length=128)
    role_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)

    @field_validator("name", "first_name", "last_name", "employee_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("email", mode="before")
    @classmethod
    def normalize_user_email(cls, value: object) -> object:
        return normalize_email(value) if isinstance(value, str) else value

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return parse_username(value)

    @model_validator(mode="after")
    def compose_identity_and_password(self) -> Self:
        display_name = self.name
        if not display_name:
            parts = [part for part in (self.first_name, self.last_name) if part]
            display_name = " ".join(parts) or None
        if not display_name:
            display_name = self.username
        object.__setattr__(self, "name", display_name)
        # Email is optional. Username is the guaranteed sign-in identifier.
        if self.email:
            object.__setattr__(self, "email", normalize_email(str(self.email).strip()))
        if self.password:
            validate_password(
                self.password,
                email=str(self.email) if self.email else None,
                name=display_name,
                username=self.username,
            )
        return self


class UserUpdateRequest(StrictRequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    username: str | None = Field(default=None, min_length=3, max_length=50)
    employee_id: str | None = Field(default=None, max_length=50)
    status: Literal["Active", "Inactive"] | None = None
    version: int = Field(ge=1)

    @field_validator("name", "employee_id")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if value != "" and not normalized:
            raise ValueError("must not be blank")
        return normalized or None

    @field_validator("username")
    @classmethod
    def normalize_optional_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return parse_username(value)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    username: str
    email: str | None
    employee_id: str | None = None
    role: str
    roles: list[str] = Field(default_factory=list)
    status: str
    version: int
    created_by_user_id: uuid.UUID | None
    last_login_at: datetime | None = None
    created_at: datetime
    temporary_password: str | None = None
