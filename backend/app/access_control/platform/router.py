from fastapi import APIRouter

from app.access_control.platform.page_access.router import router as page_access_router
from app.access_control.platform.roles.router import router as roles_router
from app.access_control.platform.users.router import router as users_router

router = APIRouter(prefix="/platform", tags=["platform-access"])
router.include_router(users_router)
router.include_router(roles_router)
router.include_router(page_access_router)
