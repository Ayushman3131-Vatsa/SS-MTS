import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.task_management.domain.enums import ProjectMemberRole
from app.schemas.base import StrictRequestModel


class ProjectMemberCreateRequest(StrictRequestModel):
    user_id: uuid.UUID
    role: ProjectMemberRole


class ProjectMemberUpdateRequest(StrictRequestModel):
    role: ProjectMemberRole


class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID
    user_id: uuid.UUID
    role: ProjectMemberRole
    added_by_user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

