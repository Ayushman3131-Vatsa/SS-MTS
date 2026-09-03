import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import (
    Principal,
    require_tenant_page_access,
    require_tenant_user,
)
from app.db.session import get_db
from app.modules.configurations import service
from app.schemas.configuration import (
    ConfigCategoryResponse,
    ConfigTemplateCatalogItem,
    ConfigTemplateDetailResponse,
    ConfigTemplateListItem,
    TemplateOverrideRequest,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
)

router = APIRouter(prefix="/config", tags=["configurations"])


@router.get("/categories", response_model=list[ConfigCategoryResponse])
async def list_categories(
    principal: Principal = Depends(require_tenant_page_access("TENANT_CONFIGURATIONS", "view")),
    db: AsyncSession = Depends(get_db),
) -> list[ConfigCategoryResponse]:
    """Return configuration categories for the tenant's licensed offerings."""
    return await service.list_config_categories(db, principal)


@router.get("/templates", response_model=list[ConfigTemplateCatalogItem])
async def list_template_catalog(
    principal: Principal = Depends(require_tenant_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConfigTemplateCatalogItem]:
    """Return templates from all offerings currently licensed to the tenant."""
    return await service.list_template_catalog(db, principal)


@router.get(
    "/categories/{category_id}/templates",
    response_model=list[ConfigTemplateListItem],
)
async def list_templates(
    category_id: uuid.UUID,
    principal: Principal = Depends(require_tenant_page_access("TENANT_CONFIGURATIONS", "view")),
    db: AsyncSession = Depends(get_db),
) -> list[ConfigTemplateListItem]:
    """Return all templates in a category with customization status."""
    return await service.list_templates(db, principal, category_id)


@router.get(
    "/templates/{template_id}",
    response_model=ConfigTemplateDetailResponse,
)
async def get_template(
    template_id: uuid.UUID,
    principal: Principal = Depends(require_tenant_page_access("TENANT_CONFIGURATIONS", "view")),
    db: AsyncSession = Depends(get_db),
) -> ConfigTemplateDetailResponse:
    """Return a single template with effective (merged) values."""
    return await service.get_effective_template(db, principal, template_id)


@router.put(
    "/templates/{template_id}/override",
    response_model=ConfigTemplateDetailResponse,
)
async def save_override(
    template_id: uuid.UUID,
    payload: TemplateOverrideRequest,
    principal: Principal = Depends(require_tenant_page_access("TENANT_CONFIGURATIONS", "modify")),
    db: AsyncSession = Depends(get_db),
) -> ConfigTemplateDetailResponse:
    """Create or update a tenant's template customization."""
    return await service.save_override(db, principal, template_id, payload)


@router.delete(
    "/templates/{template_id}/override",
    response_model=ConfigTemplateDetailResponse,
)
async def reset_override(
    template_id: uuid.UUID,
    principal: Principal = Depends(require_tenant_page_access("TENANT_CONFIGURATIONS", "modify")),
    db: AsyncSession = Depends(get_db),
) -> ConfigTemplateDetailResponse:
    """Reset a template to platform default by deleting the override."""
    return await service.reset_override(db, principal, template_id)


@router.post(
    "/templates/{template_id}/preview",
    response_model=TemplatePreviewResponse,
)
async def preview_template(
    template_id: uuid.UUID,
    payload: TemplatePreviewRequest,
    principal: Principal = Depends(require_tenant_user),
    db: AsyncSession = Depends(get_db),
) -> TemplatePreviewResponse:
    """Render the effective template with sample data for preview."""
    return await service.preview_template(
        db, principal, template_id, payload.sample_data,
    )
