from fastapi import APIRouter

from app.access_control.platform.router import router as platform_access_router
from app.access_control.tenant.router import router as tenant_access_router

router = APIRouter()
router.include_router(platform_access_router)
router.include_router(tenant_access_router)
