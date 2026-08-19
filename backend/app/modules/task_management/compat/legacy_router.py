"""Aggregate the retained legacy task-management routes in one owned boundary."""

from fastapi import APIRouter

from app.modules.comments.router import router as comments_router
from app.modules.daily_logs.router import router as daily_logs_router
from app.modules.projects.router import router as projects_router
from app.modules.tasks.router import router as tasks_router


router = APIRouter()
router.include_router(projects_router)
router.include_router(tasks_router)
router.include_router(comments_router)
router.include_router(daily_logs_router)
