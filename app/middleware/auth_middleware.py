"""Runs before every request reaches a route handler (added in app/main.py via
app.add_middleware). It only checks that a well-formed, unexpired JWT is
present — it does not touch the database. Per-request identity/role/tenant
loading (and confirming the user is still Active) happens in
app.common.deps.get_current_principal, which every protected route depends
on. Splitting it this way keeps the cheap check (signature/expiry) in front
of every request while the DB-backed check stays a normal FastAPI dependency
that shows up in OpenAPI docs.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.security import decode_access_token

PUBLIC_PATH_PREFIXES = ("/docs", "/openapi.json", "/redoc", "/health", "/auth")


class JWTGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing bearer token"})

        token = auth_header.removeprefix("Bearer ").strip()
        try:
            claims = decode_access_token(token)
        except ValueError as exc:
            return JSONResponse(status_code=401, content={"detail": str(exc)})

        request.state.jwt_claims = claims
        return await call_next(request)
