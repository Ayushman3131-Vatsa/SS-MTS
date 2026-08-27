"""Combined API surface for the Auth module — login/session endpoints plus
tenant user (account) provisioning and access-control administration."""

from fastapi import APIRouter

from app.access_control.router import router as access_control_router
from app.auth.accounts.router import router as accounts_router
from app.auth.login.router import router as login_router

router = APIRouter()
router.include_router(login_router)
router.include_router(accounts_router)
router.include_router(access_control_router)
