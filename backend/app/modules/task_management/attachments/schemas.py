import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    attachment_id: uuid.UUID
    task_id: uuid.UUID
    original_filename: str
    media_type: str
    size_bytes: int
    uploaded_by_user_id: uuid.UUID
    created_at: datetime

