from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.auth import service
from app.schemas.auth import AdminLoginRequest, TenantLoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/admin/login", response_model=TokenResponse)
async def admin_login(payload: AdminLoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    return await service.login_platform_admin(db, payload)


@router.post("/login", response_model=TokenResponse)
async def tenant_login(payload: TenantLoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    return await service.login_tenant_user(db, payload)
