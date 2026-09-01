import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.platform.schemas import (
    PlatformUserCreateRequest,
    PlatformUserResponse,
    PlatformUserRoleAssignmentRequest,
    PlatformUserUpdateRequest,
)
from app.access_control.platform.users import service
from app.auth.deps import Principal, require_platform_admin
from app.common.db.session import get_db

router = APIRouter()


@router.get("/users", response_model=list[PlatformUserResponse])
async def list_platform_users(
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[PlatformUserResponse]:
    del principal
    return await service.list_platform_users(db)


@router.post("/users", response_model=PlatformUserResponse, status_code=status.HTTP_201_CREATED)
async def create_platform_user(
    payload: PlatformUserCreateRequest,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> PlatformUserResponse:
    return await service.create_platform_user(db, actor_id=principal.id, payload=payload)


@router.patch("/users/{admin_id}", response_model=PlatformUserResponse)
async def update_platform_user(
    admin_id: uuid.UUID,
    payload: PlatformUserUpdateRequest,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> PlatformUserResponse:
    return await service.update_platform_user(
        db, actor_id=principal.id, admin_id=admin_id, payload=payload
    )


@router.put("/users/{admin_id}/roles", response_model=PlatformUserResponse)
async def assign_platform_user_roles(
    admin_id: uuid.UUID,
    payload: PlatformUserRoleAssignmentRequest,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> PlatformUserResponse:
    return await service.assign_platform_user_roles(
        db,
        actor_id=principal.id,
        admin_id=admin_id,
        role_ids=payload.role_ids,
    )
