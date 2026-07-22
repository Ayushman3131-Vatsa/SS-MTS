import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8)
    role: Literal["Project Manager", "Employee"]


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: Literal["Active", "Inactive"] | None = None
    version: int


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
