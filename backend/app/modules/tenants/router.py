import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal, require_platform_admin
from app.db.session import get_db
from app.modules.tenants import service
from app.schemas.tenant import (
    TenantCreateRequest,
    TenantRegistrationOptionsResponse,
    TenantResponse,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/registration-options", response_model=TenantRegistrationOptionsResponse)
async def get_registration_options(
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantRegistrationOptionsResponse:
    return await service.get_registration_options(db)


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreateRequest,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    tenant = await service.create_tenant(db, principal, payload)
    return TenantResponse.model_validate(tenant)


@router.get("", response_model=list[TenantResponse])
async def list_tenants(
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[TenantResponse]:
    return [TenantResponse.model_validate(t) for t in await service.list_tenants(db)]


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    tenant = await service.get_tenant_or_404(db, tenant_id)
    return TenantResponse.model_validate(tenant)
