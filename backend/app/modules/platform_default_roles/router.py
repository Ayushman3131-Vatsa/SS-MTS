import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import (
    Principal,
    require_platform_admin,
    require_platform_page_access,
)
from app.db.session import get_db
from app.modules.platform_default_roles import service
from app.modules.platform_default_roles.schemas import (
    DefaultRoleCreateRequest,
    DefaultRoleDetailResponse,
    DefaultRoleListItem,
    DefaultRolePagesResponse,
    DefaultRoleUpdateRequest,
)

router = APIRouter(
    prefix="/platform/default-roles",
    tags=["platform-default-roles"],
)


def _set_private_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get("", response_model=list[DefaultRoleListItem])
async def list_default_roles(
    response: Response,
    offering_id: uuid.UUID | None = Query(default=None),
    scope: str | None = Query(default=None),
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[DefaultRoleListItem]:
    _set_private_no_store(response)
    return await service.list_roles(
        db,
        offering_id=offering_id,
        core_only=offering_id is None and (scope or "").upper() == "CORE",
    )


@router.get("/pages", response_model=DefaultRolePagesResponse)
async def list_default_role_pages(
    response: Response,
    offering_id: uuid.UUID | None = Query(default=None),
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> DefaultRolePagesResponse:
    _set_private_no_store(response)
    return await service.list_scope_pages(db, offering_id=offering_id)


@router.get("/{role_id}", response_model=DefaultRoleDetailResponse)
async def get_default_role(
    role_id: uuid.UUID,
    response: Response,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> DefaultRoleDetailResponse:
    _set_private_no_store(response)
    return await service.get_role(db, role_id)


@router.post("", response_model=DefaultRoleDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_default_role(
    payload: DefaultRoleCreateRequest,
    response: Response,
    principal: Principal = Depends(require_platform_page_access("PLATFORM_ROLES", "modify")),
    db: AsyncSession = Depends(get_db),
) -> DefaultRoleDetailResponse:
    _set_private_no_store(response)
    return await service.create_role(db, principal, payload)


@router.patch("/{role_id}", response_model=DefaultRoleDetailResponse)
async def update_default_role(
    role_id: uuid.UUID,
    payload: DefaultRoleUpdateRequest,
    response: Response,
    principal: Principal = Depends(require_platform_page_access("PLATFORM_ROLES", "modify")),
    db: AsyncSession = Depends(get_db),
) -> DefaultRoleDetailResponse:
    _set_private_no_store(response)
    return await service.update_role(db, principal, role_id, payload)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_default_role(
    role_id: uuid.UUID,
    response: Response,
    principal: Principal = Depends(require_platform_page_access("PLATFORM_ROLES", "modify")),
    db: AsyncSession = Depends(get_db),
) -> None:
    _set_private_no_store(response)
    await service.delete_role(db, principal, role_id)
