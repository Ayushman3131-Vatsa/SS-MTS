"""Compatibility service for legacy daily progress logs."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal
from app.modules.task_management.time_entries import service as canonical_service
from app.modules.task_management.time_entries.model import DailyProgressLog
from app.modules.task_management.time_entries.schemas import TimeEntryCreateRequest
from app.schemas.daily_log import DailyLogCreateRequest


async def create_log(
    db: AsyncSession,
    principal: Principal,
    task_id: uuid.UUID,
    payload: DailyLogCreateRequest,
) -> DailyProgressLog:
    return await canonical_service.create_entry(
        db,
        principal,
        task_id,
        TimeEntryCreateRequest(
            hours_worked=payload.hours_worked,
            progress_notes=payload.progress_notes,
        ),
        legacy_attachment_url=payload.attachment_url,
    )


async def list_logs(
    db: AsyncSession, principal: Principal, task_id: uuid.UUID
) -> list[DailyProgressLog]:
    return await canonical_service.list_entries_legacy(db, principal, task_id)
