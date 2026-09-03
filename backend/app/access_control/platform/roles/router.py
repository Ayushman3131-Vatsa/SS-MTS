import uuid

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.platform.roles import service
from app.access_control.platform.users.service import list_platform_roles
from app.access_control.shared.schemas import RoleCreateRequest, RoleResponse, RoleUpdateRequest
from app.auth.deps import (
    Principal,
    require_platform_admin,
    require_platform_page_access,
)
from app.common.db.session import get_db

router = APIRouter()


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[RoleResponse]:
    del principal
    return await list_platform_roles(db)


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreateRequest,
    principal: Principal = Depends(require_platform_page_access("PLATFORM_ROLES", "modify")),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    return await service.create_platform_role(db, actor_id=principal.id, payload=payload)


@router.patch("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdateRequest,
    principal: Principal = Depends(require_platform_page_access("PLATFORM_ROLES", "modify")),
    db: AsyncSession = Depends(get_db),
) -> RoleResponse:
    del principal
    return await service.update_platform_role(db, role_id=role_id, payload=payload)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: uuid.UUID,
    principal: Principal = Depends(require_platform_page_access("PLATFORM_ROLES", "modify")),
    db: AsyncSession = Depends(get_db),
) -> Response:
    del principal
    await service.delete_platform_role(db, role_id=role_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
