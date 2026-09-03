import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.tenant.roles import service as roles_service
from app.access_control.tenant.schemas import TenantUserRoleAssignmentRequest
from app.auth.deps import (
    Principal,
    require_tenant_page_access,
)
from app.common.db.session import get_db

router = APIRouter()


@router.put("/users/{user_id}/roles", status_code=status.HTTP_204_NO_CONTENT)
async def assign_tenant_user_roles(
    user_id: uuid.UUID,
    payload: TenantUserRoleAssignmentRequest,
    principal: Principal = Depends(require_tenant_page_access("TENANT_USERS", "modify")),
    db: AsyncSession = Depends(get_db),
) -> None:
    tenant_id = roles_service.require_tenant_context(principal.tenant_id)
    await roles_service.assign_tenant_user_roles(
        db,
        tenant_id=tenant_id,
        actor_id=principal.id,
        user_id=user_id,
        role_ids=payload.role_ids,
    )
