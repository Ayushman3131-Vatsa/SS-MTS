"""Combined API surface for the Task Management module — projects, tasks,
comments, and daily progress logs. main.py mounts this single router
instead of reaching into each entity folder individually."""

from fastapi import APIRouter

from app.task_management.comments.router import router as comments_router
from app.task_management.daily_logs.router import router as daily_logs_router
from app.task_management.projects.router import router as projects_router
from app.task_management.tasks.router import router as tasks_router

router = APIRouter()
router.include_router(projects_router)
router.include_router(tasks_router)
router.include_router(comments_router)
router.include_router(daily_logs_router)
