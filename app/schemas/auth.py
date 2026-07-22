import uuid

from pydantic import BaseModel, EmailStr


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TenantLoginRequest(BaseModel):
    """email is only unique within a tenant (UNIQUE(tenant_id, email)), so a
    tenant user login must disambiguate which tenant they belong to. A real
    deployment would resolve this from a subdomain/org-slug; this POC takes
    it explicitly instead of guessing across tenants."""

    tenant_id: uuid.UUID
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    tenant_id: uuid.UUID | None = None
