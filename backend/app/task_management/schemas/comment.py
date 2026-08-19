import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.common.schemas.base import StrictRequestModel


class CommentCreateRequest(StrictRequestModel):
    comment_text: str = Field(min_length=1, max_length=20_000)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    comment_id: uuid.UUID
    task_id: uuid.UUID
    commented_by_user_id: uuid.UUID
    comment_text: str
    created_at: datetime
