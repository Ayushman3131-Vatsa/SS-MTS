import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal, require_roles, require_tenant_user
from app.db.session import get_db
from app.modules.users import service
from app.schemas.user import UserCreateRequest, UserResponse, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    principal: Principal = Depends(require_roles("Tenant Admin")),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return service.to_user_response(await service.create_user(db, principal, payload))


@router.get("", response_model=list[UserResponse])
async def list_users(
    principal: Principal = Depends(require_tenant_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    return [service.to_user_response(u) for u in await service.list_users(db, principal)]


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    principal: Principal = Depends(require_tenant_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return service.to_user_response(await service.get_user_or_404(db, principal, user_id))


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdateRequest,
    principal: Principal = Depends(require_roles("Tenant Admin")),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    return service.to_user_response(await service.update_user(db, principal, user_id, payload))
