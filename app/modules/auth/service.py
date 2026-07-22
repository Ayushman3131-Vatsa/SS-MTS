from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, verify_password
from app.models.platform_admin import PlatformAdmin
from app.models.user import User
from app.schemas.auth import AdminLoginRequest, TenantLoginRequest, TokenResponse


async def login_platform_admin(db: AsyncSession, payload: AdminLoginRequest) -> TokenResponse:
    result = await db.execute(select(PlatformAdmin).where(PlatformAdmin.email == payload.email))
    admin = result.scalar_one_or_none()
    if admin is None or not verify_password(payload.password, admin.password_hash):
        raise UnauthorizedError("Invalid email or password")

    token = create_access_token({"sub": str(admin.admin_id), "type": "admin"})
    return TokenResponse(access_token=token, role="Administrator", tenant_id=None)


async def login_tenant_user(db: AsyncSession, payload: TenantLoginRequest) -> TokenResponse:
    result = await db.execute(
        select(User).where(User.tenant_id == payload.tenant_id, User.email == payload.email)
    )
    user = result.scalar_one_or_none()
    if user is None or user.status != "Active" or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError("Invalid credentials")

    token = create_access_token(
        {"sub": str(user.user_id), "type": "user", "tenant_id": str(user.tenant_id), "role": user.role}
    )
    return TokenResponse(access_token=token, role=user.role, tenant_id=user.tenant_id)
