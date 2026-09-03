import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.common.schemas.base import StrictRequestModel
from app.models.enums import OfferingRoleType


_CODE_PATTERN = r"^[A-Z][A-Z0-9_]{1,49}$"
_SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
_ICON_PATTERN = r"^[a-z0-9-]{1,50}$"


class OfferingCatalogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    offering_id: uuid.UUID
    code: str
    display_name: str
    description: str
    icon_key: str
    route_slug: str
    sort_order: int
    status: str
    role_type: OfferingRoleType
    tenant_entitlement_count: int
    configuration_category_count: int


class _OfferingFields(StrictRequestModel):
    display_name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=5000)
    icon_key: str = Field(pattern=_ICON_PATTERN)
    route_slug: str = Field(pattern=_SLUG_PATTERN, max_length=63)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("display_name", "description")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class OfferingCreateRequest(_OfferingFields):
    code: str = Field(pattern=_CODE_PATTERN)
    status: str = Field(default="INACTIVE", pattern=r"^(ACTIVE|INACTIVE)$")
    role_type: OfferingRoleType

    @field_validator("code", "icon_key", "route_slug", mode="before")
    @classmethod
    def normalize_identifiers(cls, value: str) -> str:
        return value.strip()


class OfferingUpdateRequest(StrictRequestModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, min_length=1, max_length=5000)
    icon_key: str | None = Field(default=None, pattern=_ICON_PATTERN)
    route_slug: str | None = Field(default=None, pattern=_SLUG_PATTERN, max_length=63)
    sort_order: int | None = Field(default=None, ge=0)
    role_type: OfferingRoleType | None = None

    @field_validator("display_name", "description")
    @classmethod
    def trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("icon_key", "route_slug", mode="before")
    @classmethod
    def trim_optional_identifier(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "OfferingUpdateRequest":
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("offering fields cannot be null")
        return self


class OfferingDeleteRequest(StrictRequestModel):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value
