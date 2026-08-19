import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import StrictRequestModel


class CommentCreateRequest(StrictRequestModel):
    comment_text: str = Field(min_length=1, max_length=20_000)


class CommentUpdateRequest(StrictRequestModel):
    comment_text: str = Field(min_length=1, max_length=20_000)
    version: int = Field(ge=1)


class CommentDeleteRequest(StrictRequestModel):
    version: int = Field(ge=1)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    comment_id: uuid.UUID
    task_id: uuid.UUID
    commented_by_user_id: uuid.UUID
    comment_text: str
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

