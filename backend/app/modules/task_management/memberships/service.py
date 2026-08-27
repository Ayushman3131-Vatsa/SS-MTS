import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.checks import tenant_has_task_management_modify
from app.auth.roles import get_active_role_name
from app.common.audit import record_audit
from app.common.deps import Principal
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.modules.task_management.access import (
    assert_can_manage_project,
    assert_can_view_project,
    get_project_or_404,
    require_tenant_principal,
)
from app.modules.task_management.domain import errors
from app.modules.task_management.domain.enums import ProjectMemberRole
from app.modules.task_management.memberships import repository
from app.modules.task_management.memberships.model import ProjectMember
from app.modules.task_management.memberships.schemas import (
    ProjectMemberCreateRequest,
    ProjectMemberResponse,
    ProjectMemberUpdateRequest,
)
from app.modules.task_management.schemas import PageResponse


async def validate_member_user(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
):
    user = await repository.get_user(db, tenant_id, user_id)
    if user is None or not user.is_active:
        raise BusinessRuleError(
            "Only an active tenant user can be added to a project",
            code=errors.INVALID_PROJECT_MEMBER,
        )
    user_role = await get_active_role_name(db, user.id)
    if user_role is None:
        raise BusinessRuleError(
            "Only an active tenant user can be added to a project",
            code=errors.INVALID_PROJECT_MEMBER,
        )
    if role == ProjectMemberRole.MANAGER:
        if user_role != "Tenant Admin" and not await tenant_has_task_management_modify(
            db, tenant_id=tenant_id, user_id=user_id
        ):
            raise BusinessRuleError(
                "Only users with Task Management modify access can be a project manager",
                code=errors.INVALID_PROJECT_MEMBER,
            )
    return user


async def ensure_member(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    role: ProjectMemberRole,
    added_by_user_id: uuid.UUID,
) -> ProjectMember:
    await validate_member_user(db, tenant_id, user_id, role)
    existing = await repository.get_member(db, tenant_id, project_id, user_id)
    if existing is not None:
        if role == ProjectMemberRole.MANAGER and existing.role != ProjectMemberRole.MANAGER:
            existing.role = ProjectMemberRole.MANAGER
        return existing
    member = ProjectMember(
        tenant_id=tenant_id,
        project_id=project_id,
        user_id=user_id,
        role=role,
        added_by_user_id=added_by_user_id,
    )
    db.add(member)
    await db.flush()
    return member


async def list_members(
    db: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID,
    *,
    page: int,
    page_size: int,
) -> PageResponse[ProjectMemberResponse]:
    await get_project_or_404(db, principal, project_id)
    await assert_can_view_project(db, principal, project_id)
    members, total = await repository.list_members(
        db, principal.tenant_id, project_id, page, page_size
    )
    return PageResponse[ProjectMemberResponse](
        items=[ProjectMemberResponse.model_validate(member) for member in members],
        page=page,
        page_size=page_size,
        total=total,
    )


async def add_member(
    db: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID,
    payload: ProjectMemberCreateRequest,
) -> ProjectMember:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    project = await get_project_or_404(db, principal, project_id)
    if project.archived_at is not None:
        raise BusinessRuleError("Archived projects are read-only", code="PROJECT_ARCHIVED")
    await assert_can_manage_project(db, principal, project_id)
    if await repository.get_member(db, tenant_id, project_id, payload.user_id):
        raise ConflictError("User is already a project member", code="PROJECT_MEMBER_EXISTS")
    member = await ensure_member(
        db,
        tenant_id=tenant_id,
        project_id=project_id,
        user_id=payload.user_id,
        role=payload.role,
        added_by_user_id=actor_id,
    )
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="project_member",
        entity_id=member.membership_id,
        action="CREATE",
        changed_by_user_id=actor_id,
        new_value={"project_id": str(project_id), "user_id": str(member.user_id), "role": member.role},
    )
    await db.commit()
    await db.refresh(member)
    return member


async def update_member(
    db: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID,
    membership_id: uuid.UUID,
    payload: ProjectMemberUpdateRequest,
) -> ProjectMember:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    project = await get_project_or_404(db, principal, project_id)
    if project.archived_at is not None:
        raise BusinessRuleError("Archived projects are read-only", code="PROJECT_ARCHIVED")
    await assert_can_manage_project(db, principal, project_id)
    member = await repository.get_membership(db, tenant_id, project_id, membership_id)
    if member is None or member.project_id != project_id:
        raise NotFoundError("Project membership not found")
    await validate_member_user(db, tenant_id, member.user_id, payload.role)
    old_role = member.role
    member.role = payload.role
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="project_member",
        entity_id=membership_id,
        action="UPDATE",
        changed_by_user_id=actor_id,
        old_value={"role": old_role},
        new_value={"role": member.role},
    )
    await db.commit()
    await db.refresh(member)
    return member


async def remove_member(
    db: AsyncSession,
    principal: Principal,
    project_id: uuid.UUID,
    membership_id: uuid.UUID,
) -> None:
    tenant_id, actor_id, _ = require_tenant_principal(principal)
    project = await get_project_or_404(db, principal, project_id)
    if project.archived_at is not None:
        raise BusinessRuleError("Archived projects are read-only", code="PROJECT_ARCHIVED")
    await assert_can_manage_project(db, principal, project_id)
    member = await repository.get_membership(db, tenant_id, project_id, membership_id)
    if member is None or member.project_id != project_id:
        raise NotFoundError("Project membership not found")
    if member.user_id in {project.pm_id, project.dm_id}:
        raise BusinessRuleError(
            "Change the project's designated manager before removing this membership",
            code=errors.INVALID_PROJECT_MEMBER,
        )
    if await repository.has_active_assignments(db, tenant_id, project_id, member.user_id):
        raise BusinessRuleError(
            "Reassign or complete this user's active tasks before removing the membership",
            code=errors.INVALID_PROJECT_MEMBER,
        )
    await record_audit(
        db,
        tenant_id=tenant_id,
        entity_type="project_member",
        entity_id=membership_id,
        action="DELETE",
        changed_by_user_id=actor_id,
        old_value={"project_id": str(project_id), "user_id": str(member.user_id), "role": member.role},
    )
    await db.delete(member)
    await db.commit()
