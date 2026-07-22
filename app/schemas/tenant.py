import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class TenantCreateRequest(BaseModel):
    org_name: str = Field(min_length=1, max_length=255)
    subscription_plan: str = Field(default="Basic", max_length=50)
    tenant_admin_name: str = Field(min_length=1, max_length=255)
    tenant_admin_email: EmailStr
    tenant_admin_password: str = Field(min_length=8)


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tenant_id: uuid.UUID
    org_name: str
    subscription_plan: str
    created_by_admin_id: uuid.UUID
    created_at: datetime
