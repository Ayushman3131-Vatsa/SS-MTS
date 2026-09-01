import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.checks import (
    tenant_has_task_management_view,
    tenant_task_management_access_level,
)
from app.access_control.shared.enums import AccessLevel
from app.common.deps import Principal
from app.core.exceptions import BusinessRuleError, ForbiddenError, NotFoundError
from app.modules.task_management.domain.policies import (
    ProjectAccess,
    can_comment_or_attach,
    can_create_task,
    can_execute_task,
    can_manage_project,
    can_view_project,
)
from app.modules.task_management.memberships import repository as membership_repository
from app.modules.task_management.projects import repository as project_repository
from app.modules.task_management.projects.model import Project
from app.modules.task_management.tasks.model import Task

_ACCESS_RANK: dict[AccessLevel, int] = {"none": 0, "view": 1, "modify": 2}


def require_tenant_principal(principal: Principal) -> tuple[uuid.UUID, uuid.UUID, str]:
    if principal.type != "user" or principal.tenant_id is None or principal.role is None:
        raise ForbiddenError("Tenant user access required", code="TENANT_REQUIRED")
    return principal.tenant_id, principal.id, principal.role


async def get_project_or_404(
    db: AsyncSession, principal: Principal, project_id: uuid.UUID, *, for_update: bool = False
) -> Project:
    tenant_id, _, _ = require_tenant_principal(principal)
    project = await project_repository.get_project(
        db, tenant_id, project_id, for_update=for_update
    )
    if project is None:
        raise NotFoundError("Project not found")
    return project


async def tenant_wide_task_visibility(db: AsyncSession, principal: Principal) -> bool:
    tenant_id, user_id, tenant_role = require_tenant_principal(principal)
    if tenant_role == "Tenant Admin":
        return True
    return await tenant_has_task_management_view(db, tenant_id=tenant_id, user_id=user_id)


async def project_access(
    db: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID,
    *,
    is_assignee: bool = False,
) -> ProjectAccess:
    tenant_id, user_id, tenant_role = require_tenant_principal(principal)
    member = await membership_repository.get_member(db, tenant_id, project_id, user_id)
    access_level = await tenant_task_management_access_level(
        db, tenant_id=tenant_id, user_id=user_id
    )
    return ProjectAccess(
        tenant_role=tenant_role,
        member_role=member.role if member is not None else None,
        is_assignee=is_assignee,
        has_tenant_task_view=_ACCESS_RANK[access_level] >= _ACCESS_RANK["view"],
        has_tenant_task_modify=_ACCESS_RANK[access_level] >= _ACCESS_RANK["modify"],
    )


async def assert_can_view_project(
    db: AsyncSession, principal: Principal, project_id: uuid.UUID
) -> ProjectAccess:
    access = await project_access(db, principal, project_id)
    if not can_view_project(access):
        raise ForbiddenError("You do not have access to this project")
    return access


async def assert_can_manage_project(
    db: AsyncSession, principal: Principal, project_id: uuid.UUID
) -> ProjectAccess:
    access = await project_access(db, principal, project_id)
    if not can_manage_project(access):
        raise ForbiddenError("You do not manage this project")
    return access


async def assert_can_create_task(
    db: AsyncSession, principal: Principal, project_id: uuid.UUID
) -> ProjectAccess:
    access = await project_access(db, principal, project_id)
    if not can_create_task(access):
        raise ForbiddenError("Project membership does not allow task creation")
    return access


async def assert_can_comment_or_attach(
    db: AsyncSession, principal: Principal, project_id: uuid.UUID
) -> ProjectAccess:
    access = await project_access(db, principal, project_id)
    if not can_comment_or_attach(access):
        raise ForbiddenError("Project membership does not allow this action")
    return access


async def assert_can_execute_task(
    db: AsyncSession, principal: Principal, task: Task
) -> ProjectAccess:
    access = await project_access(
        db, principal, task.project_id, is_assignee=task.assignee_id == principal.id
    )
    if not can_execute_task(access):
        raise ForbiddenError("Only a project manager or the assignee may update task execution")
    return access


async def assert_task_is_mutable(
    db: AsyncSession, principal: Principal, task: Task
) -> Project:
    project = await get_project_or_404(db, principal, task.project_id)
    if project.archived_at is not None:
        raise BusinessRuleError("Archived projects are read-only", code="PROJECT_ARCHIVED")
    if task.archived_at is not None:
        raise BusinessRuleError("Archived tasks are read-only", code="TASK_ARCHIVED")
    return project
