import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.platform.page_access import service
from app.access_control.shared.catalog import page_response, pages_for_realm
from app.access_control.shared.schemas import PageAccessResponse, PageAccessUpdateRequest, PageResponse
from app.auth.deps import Principal, require_platform_admin
from app.common.db.session import get_db

router = APIRouter()


@router.get("/pages", response_model=list[PageResponse])
async def list_platform_pages(
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[PageResponse]:
    del principal
    return [page_response(page) for page in await pages_for_realm(db, "platform")]


@router.get("/roles/{role_id}/page-access", response_model=list[PageAccessResponse])
async def get_platform_role_page_access(
    role_id: uuid.UUID,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[PageAccessResponse]:
    del principal
    return await service.get_platform_role_page_access(db, role_id)


@router.put("/roles/{role_id}/page-access", response_model=list[PageAccessResponse])
async def save_platform_role_page_access(
    role_id: uuid.UUID,
    payload: PageAccessUpdateRequest,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[PageAccessResponse]:
    return await service.save_platform_role_page_access(
        db,
        actor_id=principal.id,
        role_id=role_id,
        payload=payload,
    )
