import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import (
    Principal,
    require_platform_admin,
    require_platform_page_access,
)
from app.db.session import get_db
from app.modules.platform_default_templates import service
from app.schemas.platform_default_template import (
    DefaultTemplateCreateRequest,
    DefaultTemplateDetailResponse,
    DefaultTemplateListItem,
    DefaultTemplatePreviewRequest,
    DefaultTemplatePreviewResponse,
    DefaultTemplateUpdateRequest,
)


router = APIRouter(
    prefix="/platform/default-templates",
    tags=["platform-default-templates"],
)


def _set_private_no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.post("/preview", response_model=DefaultTemplatePreviewResponse)
async def preview_default_template(
    payload: DefaultTemplatePreviewRequest,
    response: Response,
    principal: Principal = Depends(require_platform_admin),
) -> DefaultTemplatePreviewResponse:
    _set_private_no_store(response)
    return service.preview_template(payload)


@router.get("", response_model=list[DefaultTemplateListItem])
async def list_default_templates(
    response: Response,
    offering_id: uuid.UUID = Query(...),
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> list[DefaultTemplateListItem]:
    _set_private_no_store(response)
    return await service.list_templates(db, offering_id)


@router.get("/{template_id}", response_model=DefaultTemplateDetailResponse)
async def get_default_template(
    template_id: uuid.UUID,
    response: Response,
    principal: Principal = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
) -> DefaultTemplateDetailResponse:
    _set_private_no_store(response)
    return await service.get_template(db, template_id)


@router.post(
    "",
    response_model=DefaultTemplateDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_default_template(
    payload: DefaultTemplateCreateRequest,
    response: Response,
    principal: Principal = Depends(require_platform_page_access("PLATFORM_DEFAULT_TEMPLATES", "modify")),
    db: AsyncSession = Depends(get_db),
) -> DefaultTemplateDetailResponse:
    _set_private_no_store(response)
    return await service.create_template(db, principal, payload)


@router.patch("/{template_id}", response_model=DefaultTemplateDetailResponse)
async def update_default_template(
    template_id: uuid.UUID,
    payload: DefaultTemplateUpdateRequest,
    response: Response,
    principal: Principal = Depends(require_platform_page_access("PLATFORM_DEFAULT_TEMPLATES", "modify")),
    db: AsyncSession = Depends(get_db),
) -> DefaultTemplateDetailResponse:
    _set_private_no_store(response)
    return await service.update_template(db, principal, template_id, payload)
