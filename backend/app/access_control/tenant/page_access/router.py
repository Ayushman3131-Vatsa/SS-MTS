import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.catalog import page_response, tenant_pages_for_entitlements
from app.access_control.shared.schemas import PageAccessResponse, PageAccessUpdateRequest, PageResponse
from app.access_control.tenant.page_access import service
from app.access_control.tenant.roles.service import require_tenant_context
from app.auth.deps import (
    Principal,
    require_tenant_page_access,
)
from app.common.db.session import get_db

router = APIRouter()


@router.get("/pages", response_model=list[PageResponse])
async def list_tenant_pages(
    principal: Principal = Depends(require_tenant_page_access("TENANT_ROLES", "view")),
    db: AsyncSession = Depends(get_db),
) -> list[PageResponse]:
    tenant_id = require_tenant_context(principal.tenant_id)
    return [page_response(page) for page in await tenant_pages_for_entitlements(db, tenant_id)]


@router.get("/roles/{role_id}/page-access", response_model=list[PageAccessResponse])
async def get_tenant_role_page_access(
    role_id: uuid.UUID,
    principal: Principal = Depends(require_tenant_page_access("TENANT_ROLES", "view")),
    db: AsyncSession = Depends(get_db),
) -> list[PageAccessResponse]:
    tenant_id = require_tenant_context(principal.tenant_id)
    return await service.get_tenant_role_page_access(db, tenant_id=tenant_id, role_id=role_id)


@router.put("/roles/{role_id}/page-access", response_model=list[PageAccessResponse])
async def save_tenant_role_page_access(
    role_id: uuid.UUID,
    payload: PageAccessUpdateRequest,
    principal: Principal = Depends(require_tenant_page_access("TENANT_ROLES", "modify")),
    db: AsyncSession = Depends(get_db),
) -> list[PageAccessResponse]:
    tenant_id = require_tenant_context(principal.tenant_id)
    return await service.save_tenant_role_page_access(
        db,
        tenant_id=tenant_id,
        actor_id=principal.id,
        role_id=role_id,
        payload=payload,
    )
