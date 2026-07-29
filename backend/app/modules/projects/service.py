import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.common.authz import assert_can_manage_project, assert_can_view_project
from app.common.deps import Principal
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.project import Project
from app.modules.projects import repository
from app.schemas.project import ProjectCreateRequest, ProjectUpdateRequest


async def create_project(db: AsyncSession, principal: Principal, payload: ProjectCreateRequest) -> Project:
    if principal.role not in ("Tenant Admin", "Project Manager"):
        raise ForbiddenError("Only a Tenant Admin or Project Manager can create projects")

    project = Project(tenant_id=principal.tenant_id, **payload.model_dump())
    db.add(project)
    await db.flush()

    await record_audit(
        db,
        tenant_id=principal.tenant_id,
        entity_type="project",
        entity_id=project.project_id,
        action="CREATE",
        changed_by_user_id=principal.id,
        new_value=payload.model_dump(mode="json"),
    )
    await db.commit()
    await db.refresh(project)
    return project


async def list_projects(db: AsyncSession, principal: Principal) -> list[Project]:
    if principal.role == "Tenant Admin":
        return await repository.list_all_projects(db, principal.tenant_id)
    if principal.role == "Project Manager":
        return await repository.list_projects_managed_by(db, principal.tenant_id, principal.id)
    return await repository.list_projects_with_assigned_tasks(db, principal.tenant_id, principal.id)


async def get_project_or_404(db: AsyncSession, tenant_id: uuid.UUID, project_id: uuid.UUID) -> Project:
    project = await repository.get_project(db, tenant_id, project_id)
    if project is None:
        raise NotFoundError("Project not found")
    return project


async def get_project_for_principal(db: AsyncSession, principal: Principal, project_id: uuid.UUID) -> Project:
    project = await get_project_or_404(db, principal.tenant_id, project_id)
    await assert_can_view_project(db, principal, project)
    return project


async def update_project(
    db: AsyncSession, principal: Principal, project_id: uuid.UUID, payload: ProjectUpdateRequest
) -> Project:
    project = await get_project_or_404(db, principal.tenant_id, project_id)
    assert_can_manage_project(principal, project)

    old_value = {"name": project.name, "status": project.status, "priority": project.priority}
    update_fields = payload.model_dump(exclude={"version"}, exclude_unset=True)

    result = await db.execute(
        update(Project)
        .where(
            Project.tenant_id == principal.tenant_id,
            Project.project_id == project_id,
            Project.version == payload.version,
        )
        .values(**update_fields, version=Project.version + 1)
        .returning(Project)
    )
    updated = result.scalar_one_or_none()
    if updated is None:
        raise ConflictError("Project was modified by someone else — refresh and retry")

    await record_audit(
        db,
        tenant_id=principal.tenant_id,
        entity_type="project",
        entity_id=project_id,
        action="UPDATE",
        changed_by_user_id=principal.id,
        old_value=old_value,
        new_value=payload.model_dump(exclude={"version"}, exclude_unset=True, mode="json"),
    )
    await db.commit()
    await db.refresh(updated)
    return updated
