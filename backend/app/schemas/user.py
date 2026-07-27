import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.security import normalize_email, validate_password
from app.schemas.base import StrictRequestModel


class UserCreateRequest(StrictRequestModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["Project Manager", "Employee"]

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized

    @field_validator("email", mode="before")
    @classmethod
    def normalize_user_email(cls, value: object) -> object:
        return normalize_email(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def enforce_password_policy(self) -> Self:
        validate_password(self.password, email=str(self.email), name=self.name)
        return self


class UserUpdateRequest(StrictRequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: Literal["Active", "Inactive"] | None = None
    version: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("must not be blank")
        return normalized


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    email: str
    role: str
    status: str
    version: int
    created_by_user_id: uuid.UUID | None
    created_at: datetime
