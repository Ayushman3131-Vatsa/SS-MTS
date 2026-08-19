"""Compatibility service for the legacy /projects API.

Business rules live in app.modules.task_management.projects.service.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import Principal
from app.common.exceptions import BusinessRuleError
from app.modules.task_management.domain.enums import Priority, ProjectStatus
from app.modules.task_management.projects import service as canonical_service
from app.modules.task_management.projects.model import Project
from app.modules.task_management.projects.schemas import (
    ProjectCreateRequest as CanonicalProjectCreateRequest,
    ProjectUpdateRequest as CanonicalProjectUpdateRequest,
)
from app.task_management.schemas.project import ProjectCreateRequest, ProjectUpdateRequest


def _project_status(value: str | None, *, default: ProjectStatus) -> ProjectStatus:
    try:
        return ProjectStatus(value) if value is not None else default
    except ValueError as exc:
        raise BusinessRuleError("Invalid project status", code="PROJECT_STATUS_INVALID") from exc


def _priority(value: str | None) -> Priority:
    try:
        return Priority(value) if value is not None else Priority.MEDIUM
    except ValueError as exc:
        raise BusinessRuleError("Invalid project priority", code="PROJECT_PRIORITY_INVALID") from exc


async def create_project(
    db: AsyncSession, principal: Principal, payload: ProjectCreateRequest
) -> Project:
    canonical = CanonicalProjectCreateRequest(
        name=payload.name,
        client_name=payload.client_name,
        description=payload.description,
        start_date=payload.start_date,
        expected_end_date=payload.expected_end_date,
        status=_project_status(payload.status, default=ProjectStatus.NOT_STARTED),
        priority=_priority(payload.priority),
        pm_id=payload.pm_id,
        dm_id=payload.dm_id,
        remarks=payload.remarks,
    )
    return await canonical_service.create_project(db, principal, canonical)


async def list_projects(db: AsyncSession, principal: Principal) -> list[Project]:
    return await canonical_service.list_projects_legacy(db, principal)


async def get_project_or_404(
    db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID
) -> Project:
    # Retained for imports used by older modules. Tenant access is still
    # enforced by the repository lookup.
    project = await canonical_service.repository.get_project(db, tenant_id, project_id)
    if project is None:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Project not found")
    return project


async def get_project_for_principal(
    db: AsyncSession, principal: Principal, project_id: uuid.UUID
) -> Project:
    return await canonical_service.get_project_for_principal(db, principal, project_id)


async def update_project(
    db: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
) -> Project:
    values = payload.model_dump(exclude={"version"}, exclude_unset=True)
    if "status" in values and values["status"] is not None:
        values["status"] = _project_status(values["status"], default=ProjectStatus.NOT_STARTED)
    if "priority" in values and values["priority"] is not None:
        values["priority"] = _priority(values["priority"])
    canonical = CanonicalProjectUpdateRequest.model_validate(
        {**values, "version": payload.version}
    )
    return await canonical_service.update_project(db, principal, project_id, canonical)
