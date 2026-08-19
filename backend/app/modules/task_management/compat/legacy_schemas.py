"""Stable schema imports for compatibility adapters.

These aliases deliberately point at the historical Pydantic models so no old
request or response field is added, renamed, or removed.
"""

from app.schemas.comment import CommentCreateRequest, CommentResponse
from app.schemas.daily_log import DailyLogCreateRequest, DailyLogResponse
from app.schemas.project import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.schemas.task import TaskCreateRequest, TaskResponse, TaskUpdateRequest


__all__ = [
    "CommentCreateRequest",
    "CommentResponse",
    "DailyLogCreateRequest",
    "DailyLogResponse",
    "ProjectCreateRequest",
    "ProjectResponse",
    "ProjectUpdateRequest",
    "TaskCreateRequest",
    "TaskResponse",
    "TaskUpdateRequest",
]
