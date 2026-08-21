import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.common.security import normalize_email
from app.common.schemas.base import StrictRequestModel

LoginPassword = Annotated[str, Field(min_length=1, max_length=128)]


class StrictAuthRequest(StrictRequestModel):
    """Authentication payloads reject typos and unexpected input.

    String stripping is intentionally not enabled globally: passwords are
    exact secrets, so leading or trailing whitespace must be preserved.
    """

    @field_validator("email", mode="before", check_fields=False)
    @classmethod
    def canonicalize_email(cls, value: object) -> object:
        return normalize_email(value) if isinstance(value, str) else value


class AdminLoginRequest(StrictAuthRequest):
    email: Annotated[EmailStr, Field(max_length=254)]
    password: LoginPassword


class TenantLoginRequest(StrictAuthRequest):
    email: Annotated[EmailStr, Field(max_length=254)]
    password: LoginPassword


class PlatformSessionLoginRequest(StrictAuthRequest):
    email: Annotated[EmailStr, Field(max_length=254)]
    password: LoginPassword


class TenantSessionLoginRequest(StrictAuthRequest):
    email: Annotated[EmailStr, Field(max_length=254)]
    password: LoginPassword


class PasswordChangeRequest(StrictAuthRequest):
    current_password: LoginPassword
    new_password: LoginPassword


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    tenant_id: uuid.UUID | None = None


class SessionOfferingResponse(BaseModel):
    model_config = {"from_attributes": True}

    offering_id: uuid.UUID
    code: str
    display_name: str
    description: str
    icon_key: str
    route_slug: str
    sort_order: int


class SessionTenantResponse(BaseModel):
    tenant_id: uuid.UUID
    org_name: str
    tenant_code: str
    status: Literal["ACTIVE", "SUSPENDED"]
    offerings: list[SessionOfferingResponse]


class SessionPrincipalResponse(BaseModel):
    principal_type: Literal["platform_admin", "tenant_user"]
    principal_id: uuid.UUID
    name: str
    email: str
    role: Literal["Platform Admin", "Tenant Admin", "Project Manager", "Employee"]
    tenant: SessionTenantResponse | None
    password_change_required: bool = False


class PasswordChangeResponse(BaseModel):
    principal: SessionPrincipalResponse
    replacement_access_token: str | None = None
    token_type: Literal["bearer"] | None = None
