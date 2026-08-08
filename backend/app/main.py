from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.middleware.auth_middleware import AuthenticationMiddleware, PUBLIC_ROUTES
from app.middleware.security_middleware import (
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.modules.auth.router import router as auth_router
from app.modules.comments.router import router as comments_router
from app.modules.configurations.router import router as configurations_router
from app.modules.daily_logs.router import router as daily_logs_router
from app.modules.offerings.router import router as offerings_router
from app.modules.projects.router import router as projects_router
from app.modules.platform_dashboard.router import router as platform_dashboard_router
from app.modules.platform_default_templates.router import router as platform_default_templates_router
from app.modules.tasks.router import router as tasks_router
from app.modules.tenants.router import router as tenants_router
from app.modules.users.router import router as users_router

app = FastAPI(title="Multi-Tenant Task Management POC", version="0.1.0")

# Middleware registration is intentionally ordered from application concern to
# transport concern. Starlette makes the last registered middleware outermost:
# security headers therefore decorate every response, request-size checks run
# before authentication, and authentication runs before route handlers.
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


def _is_default_template_request(request: Request) -> bool:
    path = request.url.path
    return path == "/platform/default-templates" or path.startswith(
        "/platform/default-templates/"
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    if _is_default_template_request(request):
        headers = {"Cache-Control": "private, no-store"}
    else:
        headers = {"Cache-Control": "no-store"} if exc.status_code in {401, 403} else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "detail": exc.message},
        headers=headers,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    # FastAPI's default validation payload includes rejected input. Model-level
    # validators report their location as the whole body, so checking only for
    # a ``password`` path segment can leak an entire payload containing a
    # plaintext password. Validation responses do not need to reflect input at
    # all; omit it consistently.
    sanitized_errors: list[dict] = []
    for error in exc.errors():
        sanitized = dict(error)
        sanitized.pop("input", None)
        sanitized_errors.append(sanitized)
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(sanitized_errors)},
        headers=(
            {"Cache-Control": "private, no-store"}
            if _is_default_template_request(request)
            else (
                {"Cache-Control": "no-store"}
                if request.url.path.startswith("/auth/")
                else None
            )
        ),
    )


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(tenants_router)
app.include_router(offerings_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(platform_dashboard_router)
app.include_router(platform_default_templates_router)
app.include_router(tasks_router)
app.include_router(comments_router)
app.include_router(configurations_router)
app.include_router(daily_logs_router)


def custom_openapi() -> dict:
    """Document middleware-level authentication in Swagger/OpenAPI.

    Authentication is enforced before dependencies run, so FastAPI cannot
    infer these schemes from route signatures on its own.
    """

    if app.openapi_schema is not None:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    security_schemes = schema.setdefault("components", {}).setdefault(
        "securitySchemes",
        {},
    )
    security_schemes["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT returned by /auth/admin/login or /auth/login.",
    }
    security_schemes["BrowserSession"] = {
        "type": "apiKey",
        "in": "cookie",
        "name": get_settings().session_cookie_name,
        "description": (
            "HttpOnly browser cookie issued by a /auth/session/* login. "
            "Unsafe cookie-authenticated requests also require X-CSRF-Token."
        ),
    }

    for path, path_item in schema.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}:
                continue
            route_key = (method.upper(), path)
            operation["security"] = (
                []
                if route_key in PUBLIC_ROUTES
                else [{"BearerAuth": []}, {"BrowserSession": []}]
            )

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
