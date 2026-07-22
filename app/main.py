from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.middleware.auth_middleware import JWTGateMiddleware
from app.modules.auth.router import router as auth_router
from app.modules.comments.router import router as comments_router
from app.modules.daily_logs.router import router as daily_logs_router
from app.modules.projects.router import router as projects_router
from app.modules.tasks.router import router as tasks_router
from app.modules.tenants.router import router as tenants_router
from app.modules.users.router import router as users_router

app = FastAPI(title="Multi-Tenant Task Management POC", version="0.1.0")

# Gates every request behind a valid JWT before it reaches a route handler
# (except the public paths it carves out: /auth/*, /docs, /health, etc).
app.add_middleware(JWTGateMiddleware)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(tenants_router)
app.include_router(users_router)
app.include_router(projects_router)
app.include_router(tasks_router)
app.include_router(comments_router)
app.include_router(daily_logs_router)
