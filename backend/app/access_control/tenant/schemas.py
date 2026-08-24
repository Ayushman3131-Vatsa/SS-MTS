import uuid

from pydantic import Field

from app.common.schemas.base import StrictRequestModel


class TenantUserRoleAssignmentRequest(StrictRequestModel):
    role_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
