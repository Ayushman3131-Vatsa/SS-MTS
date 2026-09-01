import uuid

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import Principal, require_platform_admin
from app.auth.tenant_admin_onboarding import (
    enable_initial_tenant_admin,
    regenerate_initial_tenant_admin_password,
)
from app.common.db.session import get_db
from app.tenant_management.models.enums import TenantStatus
from app.tenant_management.tenants import service
from app.tenant_management.schemas.tenant import (
    TenantCreateRequest,
    TenantListResponse,
    TenantOfferingActionRequest,
    TenantOfferingGrantRequest,
    TenantOfferingRemovalRequest,
    TenantOfferingResponse,
    TenantOfferingEventResponse,
    TenantStatusActionRequest,
    TenantAdminProvisioningRequest,
    InitialTenantAdminCredentialsResponse,
    TenantRegistrationOptionsResponse,
    TenantResponse,
    TenantFirstAccessResponse,
    TenantCredentialResponse,
    OfferingCatalogResponse,
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
    created = await service.create_tenant(db, principal, payload)
    login_path = f"/t/{created.tenant.tenant_code}/login"
    return TenantResponse.model_validate(created.tenant).model_copy(
        update={
            "first_access": TenantFirstAccessResponse(
                email=created.first_admin_email,
                username=created.first_admin_username,
                temporary_password=created.temporary_password,
                login_path=login_path,
                password_change_required=True,
                smartskale_access=TenantCredentialResponse(
                    email=created.smartskale_email,
                    username=created.smartskale_username,
                    temporary_password=created.smartskale_password,
                    login_path=login_path,
                    password_change_required=False,
                ),
            )
        }
    )


@router.get("", response_model=TenantListResponse)
async def list_tenants(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    query: str | None = Query(default=None, max_length=100),
    tenant_status: str | None = Query(default=None, alias="status"),
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantListResponse:
    result = await service.list_tenants(
        db, page=page, page_size=page_size, query=query, status=tenant_status
    )
    return TenantListResponse(
        items=[TenantResponse.model_validate(t) for t in result.items],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
    )


@router.get("/offering-catalog", response_model=list[OfferingCatalogResponse])
async def list_offering_catalog(
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[OfferingCatalogResponse]:
    return [
        OfferingCatalogResponse.model_validate(offering)
        for offering in await service.list_offering_catalog(db)
    ]


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: uuid.UUID,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    tenant = await service.get_tenant_or_404(db, tenant_id)
    return TenantResponse.model_validate(tenant)


@router.post(
    "/{tenant_id}/enable",
    response_model=InitialTenantAdminCredentialsResponse,
)
async def enable_tenant(
    tenant_id: uuid.UUID,
    payload: TenantAdminProvisioningRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> InitialTenantAdminCredentialsResponse:
    credentials = await enable_initial_tenant_admin(
        db,
        tenant_id=tenant_id,
        platform_admin_id=principal.id,
        expected_version=payload.expected_version,
        idempotency_key=idempotency_key or f"tenant-enable:{tenant_id}:{payload.expected_version}",
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return InitialTenantAdminCredentialsResponse(
        email=credentials.email,
        temporary_password=credentials.temporary_password,
    )


@router.post(
    "/{tenant_id}/regenerate-initial-password",
    response_model=InitialTenantAdminCredentialsResponse,
)
async def regenerate_initial_password(
    tenant_id: uuid.UUID,
    payload: TenantAdminProvisioningRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> InitialTenantAdminCredentialsResponse:
    credentials = await regenerate_initial_tenant_admin_password(
        db,
        tenant_id=tenant_id,
        platform_admin_id=principal.id,
        expected_version=payload.expected_version,
        idempotency_key=(
            idempotency_key
            or f"tenant-regenerate-initial-password:{tenant_id}:{payload.expected_version}"
        ),
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return InitialTenantAdminCredentialsResponse(
        email=credentials.email,
        temporary_password=credentials.temporary_password,
    )


@router.post("/{tenant_id}/first-access/rotate", response_model=TenantFirstAccessResponse)
async def rotate_first_admin_access(
    tenant_id: uuid.UUID,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantFirstAccessResponse:
    rotated = await service.rotate_first_admin_access(db, principal, tenant_id)
    return TenantFirstAccessResponse(
        email=rotated.email,
        username=rotated.username,
        temporary_password=rotated.temporary_password,
    )


@router.post("/{tenant_id}/suspend", response_model=TenantResponse)
async def suspend_tenant(
    tenant_id: uuid.UUID,
    payload: TenantStatusActionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    tenant = await service.transition_tenant(
        db,
        principal,
        tenant_id,
        TenantStatus.SUSPENDED,
        payload,
        idempotency_key=idempotency_key,
    )
    return TenantResponse.model_validate(tenant)


@router.post("/{tenant_id}/activate", response_model=TenantResponse)
async def activate_tenant(
    tenant_id: uuid.UUID,
    payload: TenantStatusActionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    tenant = await service.transition_tenant(
        db,
        principal,
        tenant_id,
        TenantStatus.ACTIVE,
        payload,
        idempotency_key=idempotency_key,
    )
    return TenantResponse.model_validate(tenant)


@router.get("/{tenant_id}/offering-entitlements", response_model=list[TenantOfferingResponse])
async def list_offering_entitlements(
    tenant_id: uuid.UUID,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[TenantOfferingResponse]:
    await service.get_tenant_or_404(db, tenant_id)
    return [
        TenantOfferingResponse.model_validate(row)
        for row in await service.list_offering_entitlements(db, tenant_id)
    ]


@router.get(
    "/{tenant_id}/offering-entitlements/history",
    response_model=list[TenantOfferingEventResponse],
)
async def list_offering_history(
    tenant_id: uuid.UUID,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[TenantOfferingEventResponse]:
    await service.get_tenant_or_404(db, tenant_id)
    return [
        TenantOfferingEventResponse.model_validate(event)
        for event in await service.list_offering_events(db, tenant_id)
    ]


@router.post("/{tenant_id}/offering-entitlements", response_model=TenantOfferingResponse, status_code=status.HTTP_201_CREATED)
async def grant_offering(
    tenant_id: uuid.UUID,
    payload: TenantOfferingGrantRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantOfferingResponse:
    key = idempotency_key or f"grant:{uuid.uuid4()}"
    result = await service.grant_offering(db, principal, tenant_id, payload, idempotency_key=key)
    return TenantOfferingResponse.model_validate(result)


@router.post("/{tenant_id}/offering-entitlements/{entitlement_id}/suspend", response_model=TenantOfferingResponse)
async def suspend_offering(
    tenant_id: uuid.UUID,
    entitlement_id: uuid.UUID,
    payload: TenantOfferingActionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantOfferingResponse:
    key = idempotency_key or f"suspend:{entitlement_id}:{payload.expected_version}"
    result = await service.transition_offering(db, principal, tenant_id, entitlement_id, "suspend", payload, idempotency_key=key)
    return TenantOfferingResponse.model_validate(result)


@router.post("/{tenant_id}/offering-entitlements/{entitlement_id}/resume", response_model=TenantOfferingResponse)
async def resume_offering(
    tenant_id: uuid.UUID,
    entitlement_id: uuid.UUID,
    payload: TenantOfferingActionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantOfferingResponse:
    key = idempotency_key or f"resume:{entitlement_id}:{payload.expected_version}"
    result = await service.transition_offering(db, principal, tenant_id, entitlement_id, "resume", payload, idempotency_key=key)
    return TenantOfferingResponse.model_validate(result)


@router.post("/{tenant_id}/offering-entitlements/{entitlement_id}/deactivate", response_model=TenantOfferingResponse)
async def deactivate_offering(
    tenant_id: uuid.UUID,
    entitlement_id: uuid.UUID,
    payload: TenantOfferingActionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=255),
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> TenantOfferingResponse:
    key = idempotency_key or f"deactivate:{entitlement_id}:{payload.expected_version}"
    result = await service.transition_offering(db, principal, tenant_id, entitlement_id, "deactivate", payload, idempotency_key=key)
    return TenantOfferingResponse.model_validate(result)


@router.delete(
    "/{tenant_id}/offering-entitlements/{entitlement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_offering(
    tenant_id: uuid.UUID,
    entitlement_id: uuid.UUID,
    payload: TenantOfferingRemovalRequest,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await service.remove_retired_offering(
        db, principal, tenant_id, entitlement_id, payload
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
