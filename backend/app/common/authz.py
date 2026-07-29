"""Resource-level authorization rules, applied on top of the role check that
require_roles() already did. This maps directly to the role table in the
architecture doc: Tenant Admin has full tenant access; a Project Manager is
scoped to projects/tasks under projects they manage (pm_id/dm_id); an
Employee is scoped to tasks they are personally assigned to
(assignee/technical_lead/functional_lead).
"""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal
from app.core.exceptions import ForbiddenError
from app.models.project import Project
from app.models.task import Task


def can_manage_project(principal: Principal, project: Project) -> bool:
    if principal.role == "Tenant Admin":
        return True
    if principal.role == "Project Manager":
        return project.pm_id == principal.id or project.dm_id == principal.id
    return False


def assert_can_manage_project(principal: Principal, project: Project) -> None:
    if not can_manage_project(principal, project):
        raise ForbiddenError("You do not manage this project")


def can_access_task(principal: Principal, task: Task, project: Project) -> bool:
    if principal.role == "Tenant Admin":
        return True
    if principal.role == "Project Manager":
        return project.pm_id == principal.id or project.dm_id == principal.id
    if principal.role == "Employee":
        return principal.id in (task.assignee_id, task.technical_lead_id, task.functional_lead_id)
    return False


def assert_can_access_task(principal: Principal, task: Task, project: Project) -> None:
    if not can_access_task(principal, task, project):
        raise ForbiddenError("You are not assigned to this task")


async def can_view_project(db: AsyncSession, principal: Principal, project: Project) -> bool:
    if principal.role == "Tenant Admin":
        return True
    if principal.role == "Project Manager":
        return project.pm_id == principal.id or project.dm_id == principal.id
    if principal.role == "Employee":
        # An Employee's project access is derived, not direct: they may view
        # a project only if at least one of its tasks is assigned to them.
        result = await db.execute(
            select(Task.task_id)
            .where(
                Task.tenant_id == project.tenant_id,
                Task.project_id == project.project_id,
                or_(
                    Task.assignee_id == principal.id,
                    Task.technical_lead_id == principal.id,
                    Task.functional_lead_id == principal.id,
                ),
            )
            .limit(1)
        )
        return result.first() is not None
    return False


async def assert_can_view_project(db: AsyncSession, principal: Principal, project: Project) -> None:
    if not await can_view_project(db, principal, project):
        raise ForbiddenError("You do not have access to this project")
