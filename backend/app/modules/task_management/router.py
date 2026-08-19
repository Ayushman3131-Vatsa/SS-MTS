from fastapi import APIRouter, Depends

from app.common.deps import require_offering
from app.modules.task_management.activity.router import router as activity_router
from app.modules.task_management.attachments.router import router as attachment_router
from app.modules.task_management.comments.router import router as comment_router
from app.modules.task_management.projects.router import router as project_router
from app.modules.task_management.tasks.router import router as task_router
from app.modules.task_management.time_entries.router import router as time_router


router = APIRouter(
    prefix="/task-management",
    dependencies=[Depends(require_offering("TASK_MANAGEMENT"))],
)
router.include_router(project_router)
router.include_router(task_router)
router.include_router(comment_router)
router.include_router(time_router)
router.include_router(attachment_router)
router.include_router(activity_router)

