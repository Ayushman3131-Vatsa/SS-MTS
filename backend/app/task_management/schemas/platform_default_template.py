import re
import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.tenant_management.models.enums import ConfigTemplateType
from app.common.schemas.base import StrictRequestModel


PLACEHOLDER_KEY_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"
TEMPLATE_CODE_PATTERN = r"^[a-z][a-z0-9_]{0,99}$"
PLACEHOLDER_TOKEN_RE = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")


class DefaultTemplatePlaceholder(StrictRequestModel):
    key: str = Field(pattern=PLACEHOLDER_KEY_PATTERN)
    label: str = Field(min_length=1, max_length=100)
    sample_value: str = Field(max_length=1000)
    required: bool = False

    @field_validator("key", "label", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        # Preserve non-string inputs so Pydantic can report a normal 422 type
        # error instead of leaking AttributeError from this normalizer.
        return value.strip() if isinstance(value, str) else value

    @field_validator("label")
    @classmethod
    def reject_blank_label(cls, value: str) -> str:
        if not value:
            raise ValueError("label must not be blank")
        return value


def validate_template_content(
    subject: str | None,
    body: str,
    placeholders: list[DefaultTemplatePlaceholder],
) -> None:
    """Validate token syntax, declarations, and required placeholders."""
    keys = [placeholder.key for placeholder in placeholders]
    duplicate_keys = sorted({key for key in keys if keys.count(key) > 1})
    if duplicate_keys:
        raise ValueError(
            "placeholder keys must be unique: " + ", ".join(duplicate_keys)
        )

    content = f"{subject or ''}\n{body}"
    if "{{{" in content or "}}}" in content:
        raise ValueError("template contains a malformed placeholder token")
    token_keys = set(PLACEHOLDER_TOKEN_RE.findall(content))
    without_valid_tokens = PLACEHOLDER_TOKEN_RE.sub("", content)
    if "{{" in without_valid_tokens or "}}" in without_valid_tokens:
        raise ValueError("template contains a malformed placeholder token")

    declared_keys = set(keys)
    undeclared = sorted(token_keys - declared_keys)
    if undeclared:
        raise ValueError(
            "template uses undeclared placeholders: " + ", ".join(undeclared)
        )
    required_keys = {
        placeholder.key for placeholder in placeholders if placeholder.required
    }
    missing_required = sorted(required_keys - token_keys)
    if missing_required:
        raise ValueError(
            "template is missing required placeholders: "
            + ", ".join(missing_required)
        )


class _TemplateContentRequest(StrictRequestModel):
    subject: str | None = Field(default=None, max_length=500)
    body: str = Field(min_length=1, max_length=50_000)
    placeholders: list[DefaultTemplatePlaceholder] = Field(
        default_factory=list,
        max_length=100,
    )

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("body")
    @classmethod
    def reject_blank_body(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("body must not be blank")
        return value

    @model_validator(mode="after")
    def validate_placeholders(self) -> Self:
        validate_template_content(self.subject, self.body, self.placeholders)
        return self


class DefaultTemplateCreateRequest(_TemplateContentRequest):
    offering_id: uuid.UUID
    code: str = Field(pattern=TEMPLATE_CODE_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    type: ConfigTemplateType
    sort_order: int = Field(default=0, ge=0)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()


class DefaultTemplateUpdateRequest(StrictRequestModel):
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    subject: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, min_length=1, max_length=50_000)
    placeholders: list[DefaultTemplatePlaceholder] | None = Field(
        default=None,
        max_length=100,
    )
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("description")
    @classmethod
    def normalize_optional_description(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("subject")
    @classmethod
    def normalize_optional_subject(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("body")
    @classmethod
    def reject_optional_blank_body(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("body must not be blank")
        return value

    @model_validator(mode="after")
    def validate_safe_patch(self) -> Self:
        mutable_fields = self.model_fields_set - {"expected_version"}
        if not mutable_fields:
            raise ValueError("provide at least one template field to update")
        nullable_fields = {"subject"}
        if any(
            getattr(self, field_name) is None
            for field_name in mutable_fields - nullable_fields
        ):
            raise ValueError("template update fields cannot be null")
        return self


class DefaultTemplatePreviewRequest(_TemplateContentRequest):
    sample_data: dict[str, str] = Field(default_factory=dict, max_length=100)

    @model_validator(mode="after")
    def validate_sample_data(self) -> Self:
        unknown_keys = sorted(
            set(self.sample_data) - {placeholder.key for placeholder in self.placeholders}
        )
        if unknown_keys:
            raise ValueError(
                "sample_data contains unknown placeholders: "
                + ", ".join(unknown_keys)
            )
        return self


class DefaultTemplatePreviewResponse(BaseModel):
    subject: str | None
    rendered_body: str


class DefaultTemplateListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    template_id: uuid.UUID
    offering_id: uuid.UUID
    offering_code: str
    offering_name: str
    category_id: uuid.UUID
    category_code: str
    category_name: str
    code: str
    name: str
    description: str
    type: ConfigTemplateType
    subject: str | None
    sort_order: int
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime
    inheriting_tenant_count: int
    customized_tenant_count: int


class DefaultTemplateDetailResponse(DefaultTemplateListItem):
    body: str
    placeholders: list[DefaultTemplatePlaceholder]
