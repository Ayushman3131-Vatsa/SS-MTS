import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.checks import tenant_has_task_management_modify
from app.common.audit import record_audit
from app.common.deps import Principal
from app.core.exceptions import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.modules.task_management.access import (
    assert_can_manage_project,
    assert_can_view_project,
    get_project_or_404,
    require_tenant_principal,
    tenant_wide_task_visibility,
)
from app.modules.task_management.domain import errors
from app.modules.task_management.domain.enums import ProjectMemberRole, ProjectStatus
from app.modules.task_management.domain.transitions import can_transition_project
from app.modules.task_management.memberships.service import ensure_member, validate_member_user
from app.modules.task_management.projects import repository
from app.modules.task_management.projects.model import Project
from app.modules.task_management.projects.schemas import (
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
)
from app.modules.task_management.schemas import PageResponse


async def _generate_project_key(db: AsyncSession, tenant_id: uuid.UUID, name: str) -> str:
    base = re.sub(r"[^A-Z0-9]", "", name.upper())[:8]
    if not base or not base[0].isalpha():
        base = f"P{base}"
    if len(base) < 2:
        base = f"{base}R"
    if not await repository.project_key_exists(db, tenant_id, base):
        return base
    for suffix in range(2, 10_000):
        candidate = f"{base[: 10 - len(str(suffix))]}{suffix}"
        if not await repository.project_key_exists(db, tenant_id, candidate):
            return candidate
    raise ConflictError("Could not allocate a unique project key", code=errors.PROJECT_KEY_CONFLICT)


async def _validate_manager_ids(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    manager_ids: set[uuid.UUID],
) -> None:
    for user_id in manager_ids:
        await validate_member_user(db, tenant_id, user_id, ProjectMemberRole.MANAGER)


async def create_project(
    db: AsyncSession, principal: Principal, payload: ProjectCreateRequest
) -> Project:
    tenant_id, actor_id, tenant_role = require_tenant_principal(principal)
    has_task_modify = await tenant_has_task_management_modify(
        db, tenant_id=tenant_id, user_id=actor_id
    )
    if tenant_role != "Tenant Admin" and not has_task_modify:
        raise ForbiddenError(
            "You need modify access on Task Management to create projects"
        )

    acts_as_project_manager = tenant_role != "Tenant Admin" and has_task_modify
    pm_id = payload.pm_id
    if acts_as_project_manager and pm_id is None:
        pm_id = actor_id
    manager_ids = {value for value in (pm_id, payload.dm_id) if value is not None}
    await _validate_manager_ids(db, tenant_id, manager_ids)

    project_key = payload.project_key or await _generate_project_key(db, tenant_id, payload.name)
    if await repository.project_key_exists(db, tenant_id, project_key):
        raise ConflictError("Project key is already in use", code=errors.PROJECT_KEY_CONFLICT)

    values = payload.model_dump(exclude={"project_key", "pm_id"}, mode="python")
    project = Project(
        tenant_id=tenant_id,
        project_key=project_key,
        pm_id=pm_id,
        **values,
    )
    db.add(project)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            "Project key is already in use", code=errors.PROJECT_KEY_CONFLICT
        ) from exc

    if acts_as_project_manager:
        manager_ids.add(actor_id)
    for manager_id in manager_ids:
        await ensure_member(
            db,
            tenant_id=tenant_id,
            project_id=project.project_id,
            user_id=manager_id,
            role=ProjectMemberRole.MANAGER,
            added_by_user_id=actor_id,
        )

    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="project",
        entity_id=project.project_id,
        action="CREATE",
        changed_by_user_id=actor_id,
        new_value={
            **payload.model_dump(mode="json"),
            "project_key": project_key,
            "pm_id": str(pm_id) if pm_id else None,
        },
    )
    await db.commit()
    await db.refresh(project)
    return project


async def list_projects(
    db: AsyncSession,
    principal: Principal,
    *,
    page: int,
    page_size: int,
    query: str | None = None,
    status: str | None = None,
    member_id: uuid.UUID | None = None,
    include_archived: bool = False,
    sort: str = "-updated_at",
) -> PageResponse[ProjectResponse]:
    tenant_id, actor_id, tenant_role = require_tenant_principal(principal)
    tenant_wide_access = await tenant_wide_task_visibility(db, principal)
    projects, total = await repository.list_projects(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        tenant_wide_access=tenant_wide_access,
        page=page,
        page_size=page_size,
        query=query,
        status=status,
        member_id=member_id,
        include_archived=include_archived,
        sort=sort,
    )
    return PageResponse[ProjectResponse](
        items=[ProjectResponse.model_validate(project) for project in projects],
        page=page,
        page_size=page_size,
        total=total,
    )


async def list_projects_legacy(db: AsyncSession, principal: Principal) -> list[Project]:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    tenant_wide_access = await tenant_wide_task_visibility(db, principal)
    projects, _ = await repository.list_projects(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        tenant_wide_access=tenant_wide_access,
        page=1,
        page_size=1_000_000,
        include_archived=False,
        sort="project_key",
    )
    return projects


async def get_project_for_principal(
    db: AsyncSession, principal: Principal, project_id: uuid.UUID
) -> Project:
    project = await get_project_or_404(db, principal, project_id)
    await assert_can_view_project(db, principal, project_id)
    return project


async def update_project(
    db: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID,
    payload: ProjectUpdateRequest,
) -> Project:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    project = await get_project_or_404(db, principal, project_id)
    await assert_can_manage_project(db, principal, project_id)
    if project.archived_at is not None:
        raise BusinessRuleError("Restore the project before updating it", code="PROJECT_ARCHIVED")
    update_fields = payload.model_dump(exclude={"version"}, exclude_unset=True, mode="python")
    if not update_fields:
        raise BusinessRuleError("Provide at least one project field to update", code="PROJECT_UPDATE_EMPTY")

    start_date = update_fields.get("start_date", project.start_date)
    end_date = update_fields.get("expected_end_date", project.expected_end_date)
    if start_date is not None and end_date is not None and end_date < start_date:
        raise BusinessRuleError("expected_end_date must be on or after start_date", code="PROJECT_DATE_ORDER")
    if "status" in update_fields and not can_transition_project(project.status, str(update_fields["status"])):
        raise BusinessRuleError(
            f"Project cannot transition from {project.status} to {update_fields['status']}",
            code=errors.INVALID_PROJECT_TRANSITION,
        )
    if (
        update_fields.get("status") == ProjectStatus.COMPLETED
        and await repository.has_incomplete_tasks(db, tenant_id, project_id)
    ):
        raise BusinessRuleError(
            "Complete or cancel all active tasks before completing the project",
            code="PROJECT_HAS_INCOMPLETE_TASKS",
        )

    manager_ids = {
        value
        for value in (
            update_fields.get("pm_id", project.pm_id),
            update_fields.get("dm_id", project.dm_id),
        )
        if value is not None
    }
    await _validate_manager_ids(db, tenant_id, manager_ids)
    old_value = {
        "name": project.name,
        "status": project.status,
        "priority": project.priority,
        "pm_id": str(project.pm_id) if project.pm_id else None,
        "dm_id": str(project.dm_id) if project.dm_id else None,
    }
    result = await db.execute(
        update(Project)
        .where(
            Project.tenant_id == tenant_id,
            Project.project_id == project_id,
            Project.version == payload.version,
        )
        .values(**update_fields, version=Project.version + 1, updated_at=func.now())
        .returning(Project)
    )
    updated = result.scalar_one_or_none()
    if updated is None:
        raise ConflictError("Project was modified by someone else — refresh and retry")

    for manager_id in manager_ids:
        await ensure_member(
            db,
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=manager_id,
            role=ProjectMemberRole.MANAGER,
            added_by_user_id=actor_id,
        )
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="project",
        entity_id=project_id,
        action="UPDATE",
        changed_by_user_id=actor_id,
        old_value=old_value,
        new_value=payload.model_dump(exclude={"version"}, exclude_unset=True, mode="json"),
    )
    await db.commit()
    await db.refresh(updated)
    return updated


async def set_project_archived(
    db: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID,
    *,
    version: int,
    archived: bool,
) -> Project:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    project = await get_project_or_404(db, principal, project_id)
    await assert_can_manage_project(db, principal, project_id)
    archived_at = datetime.now(timezone.utc) if archived else None
    previous_archived_at = project.archived_at
    result = await db.execute(
        update(Project)
        .where(
            Project.tenant_id == tenant_id,
            Project.project_id == project_id,
            Project.version == version,
        )
        .values(archived_at=archived_at, version=Project.version + 1, updated_at=func.now())
        .returning(Project)
    )
    updated = result.scalar_one_or_none()
    if updated is None:
        raise ConflictError("Project was modified by someone else — refresh and retry")
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="project",
        entity_id=project_id,
        action="ARCHIVE" if archived else "RESTORE",
        changed_by_user_id=actor_id,
        old_value={
            "archived_at": previous_archived_at.isoformat() if previous_archived_at else None
        },
        new_value={"archived_at": archived_at.isoformat() if archived_at else None},
    )
    await db.commit()
    await db.refresh(updated)
    return updated
