import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    task_id: uuid.UUID
    event_type: str
    actor_user_id: uuid.UUID | None
    data: dict
    occurred_at: datetime

