from dataclasses import dataclass

from app.modules.task_management.domain.enums import ProjectMemberRole


@dataclass(frozen=True)
class ProjectAccess:
    tenant_role: str
    member_role: str | None
    is_assignee: bool = False


def can_view_project(access: ProjectAccess) -> bool:
    return access.tenant_role == "Tenant Admin" or access.member_role is not None


def can_manage_project(access: ProjectAccess) -> bool:
    return access.tenant_role == "Tenant Admin" or access.member_role == ProjectMemberRole.MANAGER


def can_create_task(access: ProjectAccess) -> bool:
    return can_manage_project(access) or access.member_role == ProjectMemberRole.MEMBER


def can_comment_or_attach(access: ProjectAccess) -> bool:
    return can_manage_project(access) or access.member_role == ProjectMemberRole.MEMBER


def can_execute_task(access: ProjectAccess) -> bool:
    return can_manage_project(access) or access.is_assignee

