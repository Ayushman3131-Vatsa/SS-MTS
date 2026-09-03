import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.tenant_management.models.enums import ConfigCategoryStatus, ConfigTemplateType
from app.common.schemas.base import StrictRequestModel


# ── Response models ──────────────────────────────────────────────


class ConfigCategoryResponse(BaseModel):
    """Category returned to tenants — includes the parent offering name."""

    model_config = ConfigDict(from_attributes=True)

    category_id: uuid.UUID
    offering_id: uuid.UUID
    offering_code: str
    offering_display_name: str
    code: str
    display_name: str
    description: str
    icon_key: str
    sort_order: int
    status: ConfigCategoryStatus
    template_count: int = 0


class ConfigTemplateListItem(BaseModel):
    """Lightweight template summary for list views (body excluded)."""

    model_config = ConfigDict(from_attributes=True)

    template_id: uuid.UUID
    category_id: uuid.UUID
    code: str
    display_name: str
    description: str
    template_type: ConfigTemplateType
    subject: str | None
    is_active: bool
    sort_order: int
    is_customized: bool = False


class ConfigTemplateCatalogItem(ConfigTemplateListItem):
    """Tenant-visible template summary with category and offering context."""

    offering_id: uuid.UUID
    offering_code: str
    offering_name: str
    category_name: str
    created_at: datetime


class ConfigTemplateDetailResponse(BaseModel):
    """Full template detail — includes the effective subject, body, and metadata."""

    model_config = ConfigDict(from_attributes=True)

    template_id: uuid.UUID
    category_id: uuid.UUID
    code: str
    display_name: str
    description: str
    template_type: ConfigTemplateType
    subject: str | None
    body: str
    placeholders: list[dict]
    metadata: dict
    is_active: bool
    sort_order: int
    is_customized: bool = False
    default_subject: str | None = None
    default_body: str | None = None


class TemplatePreviewResponse(BaseModel):
    """Rendered preview of a template with sample data."""

    subject: str | None
    rendered_body: str


# ── Request models ───────────────────────────────────────────────


class TemplateOverrideRequest(StrictRequestModel):
    """Create or update a tenant's template customization."""

    subject: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, max_length=50_000)
    metadata: dict | None = Field(default=None)
    is_active: bool | None = Field(default=None)


class TemplatePreviewRequest(StrictRequestModel):
    """Sample data for rendering a template preview."""

    sample_data: dict[str, str] = Field(default_factory=dict)
