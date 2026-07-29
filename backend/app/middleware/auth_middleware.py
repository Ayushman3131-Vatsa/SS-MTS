"""Authentication transport gate for bearer and browser-session clients.

Route dependencies remain responsible for loading the current account and
checking that it is still active. This middleware validates the transport
credential early and supplies a uniform claims context to those dependencies.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import db_manager
from app.modules.auth import service as auth_service

# Do not use a prefix such as "/auth": newly added auth routes must be private
# by default. These are the only credential-issuing routes.
PUBLIC_ROUTES = frozenset(
    {
        ("POST", "/auth/admin/login"),
        ("POST", "/auth/login"),
        ("POST", "/auth/session/platform"),
        ("POST", "/auth/session/tenant"),
        ("GET", "/health"),
        ("HEAD", "/health"),
        ("GET", "/health/ready"),
        ("HEAD", "/health/ready"),
        ("GET", "/docs"),
        ("GET", "/docs/"),
        ("GET", "/docs/oauth2-redirect"),
        ("GET", "/openapi.json"),
        ("GET", "/redoc"),
    }
)
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
LOGOUT_ROUTE = ("DELETE", "/auth/session")


def _clear_auth_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        settings.csrf_cookie_name,
        path="/",
        secure=settings.secure_cookies,
        httponly=False,
        samesite="lax",
    )


def _authentication_error(detail: str, *, clear_cookies: bool = False) -> JSONResponse:
    response = JSONResponse(
        status_code=401,
        content={"detail": detail},
        headers={"Cache-Control": "no-store"},
    )
    if clear_cookies:
        _clear_auth_cookies(response)
    return response


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        route_key = (request.method.upper(), request.url.path)
        if request.method == "OPTIONS" or route_key in PUBLIC_ROUTES:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header:
            if not auth_header.startswith("Bearer "):
                return _authentication_error("Unsupported authorization scheme")
            token = auth_header.removeprefix("Bearer ").strip()
            if not token:
                return _authentication_error("Missing bearer token")
            try:
                claims = decode_access_token(token)
            except ValueError:
                return _authentication_error("Invalid or expired bearer token")

            request.state.auth_method = "bearer"
            request.state.jwt_claims = claims
            return await call_next(request)

        settings = get_settings()
        session_token = request.cookies.get(settings.session_cookie_name)
        if not session_token:
            if route_key == LOGOUT_ROUTE:
                return await call_next(request)
            return _authentication_error("Authentication required")

        async with db_manager.session_for() as db:
            browser_session = await auth_service.get_active_browser_session(db, session_token)
            if browser_session is None:
                if route_key == LOGOUT_ROUTE:
                    return await call_next(request)
                return _authentication_error("Authentication required", clear_cookies=True)

            if request.method in UNSAFE_METHODS and not auth_service.browser_session_csrf_is_valid(
                browser_session,
                request.cookies.get(settings.csrf_cookie_name),
                request.headers.get("X-CSRF-Token"),
            ):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF token missing or invalid"},
                    headers={"Cache-Control": "no-store"},
                )

            if browser_session.principal_type == "platform_admin":
                claims = {
                    "sub": str(browser_session.principal_id),
                    "type": "admin",
                }
            elif browser_session.principal_type == "tenant_user" and browser_session.tenant_id is not None:
                claims = {
                    "sub": str(browser_session.principal_id),
                    "type": "user",
                    "tenant_id": str(browser_session.tenant_id),
                }
            else:
                return _authentication_error("Authentication required", clear_cookies=True)

            request.state.auth_method = "browser_session"
            request.state.browser_session_id = browser_session.session_id
            request.state.jwt_claims = claims
            await auth_service.touch_browser_session(db, browser_session)

        return await call_next(request)


# Keep the old import name available to deployments importing it directly.
JWTGateMiddleware = AuthenticationMiddleware
