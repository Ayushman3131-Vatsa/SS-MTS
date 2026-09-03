import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal, require_platform_admin
from app.db.session import get_db
from app.models.enums import OfferingRoleType
from app.modules.offerings import service
from app.schemas.offering import OfferingCatalogResponse, OfferingCreateRequest, OfferingDeleteRequest, OfferingUpdateRequest


router = APIRouter(prefix="/offerings", tags=["offerings"])


@router.get("", response_model=list[OfferingCatalogResponse])
async def list_offerings(
    query: str | None = Query(default=None, max_length=200),
    role_type: OfferingRoleType | None = Query(default=None),
    offering_status: Literal["ACTIVE", "INACTIVE"] | None = Query(
        default=None,
        alias="status",
    ),
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[OfferingCatalogResponse]:
    items = await service.list_catalog(
        db,
        query=query.strip() if query and query.strip() else None,
        role_type=role_type.value if role_type else None,
        status=offering_status,
    )
    return [OfferingCatalogResponse.model_validate(item) for item in items]


@router.post("", response_model=OfferingCatalogResponse, status_code=status.HTTP_201_CREATED)
async def create_offering(
    payload: OfferingCreateRequest,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> OfferingCatalogResponse:
    return OfferingCatalogResponse.model_validate(await service.create(db, principal, payload))


@router.patch("/{offering_id}", response_model=OfferingCatalogResponse)
async def update_offering(
    offering_id: uuid.UUID,
    payload: OfferingUpdateRequest,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> OfferingCatalogResponse:
    return OfferingCatalogResponse.model_validate(await service.update(db, principal, offering_id, payload))


@router.post("/{offering_id}/activate", response_model=OfferingCatalogResponse)
async def activate_offering(
    offering_id: uuid.UUID,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> OfferingCatalogResponse:
    return OfferingCatalogResponse.model_validate(await service.set_status(db, principal, offering_id, "ACTIVE"))


@router.post("/{offering_id}/deactivate", response_model=OfferingCatalogResponse)
async def deactivate_offering(
    offering_id: uuid.UUID,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> OfferingCatalogResponse:
    return OfferingCatalogResponse.model_validate(await service.set_status(db, principal, offering_id, "INACTIVE"))


@router.delete("/{offering_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_offering(
    offering_id: uuid.UUID,
    payload: OfferingDeleteRequest,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await service.remove(db, principal, offering_id, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
