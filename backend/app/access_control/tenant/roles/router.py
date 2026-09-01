import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.schemas import RoleCreateRequest, RoleResponse, RoleUpdateRequest
from app.access_control.tenant.roles import service
from app.auth.deps import Principal, require_roles
from app.common.db.session import get_db

router = APIRouter()


@router.get("/roles", response_model=list[RoleResponse])
async def list_tenant_roles(
    principal: Principal = Depends(require_roles("Tenant Admin")),
    db: AsyncSession = Depends(get_db),
) -> list[RoleResponse]:
    tenant_id = service.require_tenant_context(principal.tenant_id)
    return await service.list_tenant_roles(db, tenant_id)


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_role(
    payload: RoleCreateRequest,
    principal: Principal = Depends(require_roles("Tenant Admin")),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    tenant_id = service.require_tenant_context(principal.tenant_id)
    return await service.create_tenant_role(
        db,
        tenant_id=tenant_id,
        actor_id=principal.id,
        payload=payload,
    )


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_tenant_role(
    role_id: uuid.UUID,
    payload: RoleUpdateRequest,
    principal: Principal = Depends(require_roles("Tenant Admin")),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    tenant_id = service.require_tenant_context(principal.tenant_id)
    return await service.update_tenant_role(
        db,
        tenant_id=tenant_id,
        actor_id=principal.id,
        role_id=role_id,
        payload=payload,
    )


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_role(
    role_id: uuid.UUID,
    principal: Principal = Depends(require_roles("Tenant Admin")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    tenant_id = service.require_tenant_context(principal.tenant_id)
    await service.delete_tenant_role(
        db,
        tenant_id=tenant_id,
        actor_id=principal.id,
        role_id=role_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
