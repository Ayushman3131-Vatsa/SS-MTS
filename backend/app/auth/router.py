"""Combined API surface for the Auth module — login/session endpoints plus
tenant user (account) provisioning. main.py mounts this single router
instead of reaching into auth/login and auth/accounts individually."""

from fastapi import APIRouter

from app.auth.accounts.router import router as accounts_router
from app.auth.login.router import router as login_router

router = APIRouter()
router.include_router(login_router)
router.include_router(accounts_router)
