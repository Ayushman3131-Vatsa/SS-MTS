"""Business logic for the configuration/template system.

Orchestrates repository calls, enforces authorization (Tenant Admin only),
validates placeholder integrity, and implements the template resolution
(default + override merge) and Markdown preview rendering.
"""

import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.audit import record_audit
from app.common.deps import Principal
from app.core.exceptions import BusinessRuleError, ForbiddenError, NotFoundError
from app.modules.configurations import repository
from app.schemas.configuration import (
    ConfigCategoryResponse,
    ConfigTemplateDetailResponse,
    ConfigTemplateListItem,
    TemplateOverrideRequest,
    TemplatePreviewResponse,
)

PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _require_tenant_admin(principal: Principal) -> None:
    """Guard that only Tenant Admin can access configuration endpoints."""
    if principal.type != "user" or principal.role != "Tenant Admin":
        raise ForbiddenError("Only a Tenant Admin can manage configurations")


# ── Categories ───────────────────────────────────────────────────


async def list_config_categories(
    db: AsyncSession,
    principal: Principal,
) -> list[ConfigCategoryResponse]:
    """Return configuration categories for the tenant's licensed offerings."""
    _require_tenant_admin(principal)

    rows = await repository.get_categories_for_tenant(db, principal.tenant_id)
    return [ConfigCategoryResponse(**row) for row in rows]


# ── Templates ────────────────────────────────────────────────────


async def list_templates(
    db: AsyncSession,
    principal: Principal,
    category_id: uuid.UUID,
) -> list[ConfigTemplateListItem]:
    """Return all templates in a category, verifying tenant access."""
    _require_tenant_admin(principal)

    has_access = await repository.verify_category_belongs_to_tenant(
        db, category_id, principal.tenant_id,
    )
    if not has_access:
        raise NotFoundError("Configuration category not found")

    rows = await repository.get_templates_by_category(
        db, category_id, principal.tenant_id,
    )
    return [ConfigTemplateListItem(**row) for row in rows]


async def get_effective_template(
    db: AsyncSession,
    principal: Principal,
    template_id: uuid.UUID,
) -> ConfigTemplateDetailResponse:
    """Return merged template (default + override) for this tenant."""
    _require_tenant_admin(principal)

    default = await repository.get_template_by_id(db, template_id)
    if default is None:
        raise NotFoundError("Template not found")

    # Verify the template's category belongs to one of the tenant's offerings
    has_access = await repository.verify_category_belongs_to_tenant(
        db, default.category_id, principal.tenant_id,
    )
    if not has_access:
        raise NotFoundError("Template not found")

    override = await repository.get_tenant_override(
        db, principal.tenant_id, template_id,
    )

    if override is not None:
        effective_subject = override.subject if override.subject is not None else default.subject
        effective_body = override.body if override.body is not None else default.body
        effective_metadata = (
            {**(default.metadata_ or {}), **(override.metadata_ or {})}
            if override.metadata_ is not None
            else (default.metadata_ or {})
        )
        effective_is_active = override.is_active
        is_customized = True
    else:
        effective_subject = default.subject
        effective_body = default.body
        effective_metadata = default.metadata_ or {}
        effective_is_active = default.is_active
        is_customized = False

    return ConfigTemplateDetailResponse(
        template_id=default.template_id,
        category_id=default.category_id,
        code=default.code,
        display_name=default.display_name,
        description=default.description,
        template_type=default.template_type,
        subject=effective_subject,
        body=effective_body,
        placeholders=default.placeholders if isinstance(default.placeholders, list) else [],
        metadata=effective_metadata,
        is_active=effective_is_active,
        sort_order=default.sort_order,
        is_customized=is_customized,
        default_subject=default.subject,
        default_body=default.body,
    )


async def save_override(
    db: AsyncSession,
    principal: Principal,
    template_id: uuid.UUID,
    payload: TemplateOverrideRequest,
) -> ConfigTemplateDetailResponse:
    """Create or update a tenant's template customization."""
    _require_tenant_admin(principal)

    default = await repository.get_template_by_id(db, template_id)
    if default is None:
        raise NotFoundError("Template not found")

    has_access = await repository.verify_category_belongs_to_tenant(
        db, default.category_id, principal.tenant_id,
    )
    if not has_access:
        raise NotFoundError("Template not found")

    # Validate that required placeholders are still present in the body
    if payload.body is not None:
        _validate_placeholders(default, payload.body)

    await repository.upsert_override(
        db,
        tenant_id=principal.tenant_id,
        template_id=template_id,
        user_id=principal.id,
        subject=payload.subject,
        body=payload.body,
        metadata=payload.metadata,
        is_active=payload.is_active,
    )

    await record_audit(
        db,
        tenant_id=principal.tenant_id,
        entity_type="config_template_override",
        entity_id=template_id,
        action="UPSERT",
        changed_by_user_id=principal.id,
        new_value=payload.model_dump(exclude_none=True, mode="json"),
    )
    await db.commit()

    # Return the freshly resolved effective template
    return await get_effective_template(db, principal, template_id)


async def reset_override(
    db: AsyncSession,
    principal: Principal,
    template_id: uuid.UUID,
) -> ConfigTemplateDetailResponse:
    """Delete the tenant's override, resetting to platform default."""
    _require_tenant_admin(principal)

    default = await repository.get_template_by_id(db, template_id)
    if default is None:
        raise NotFoundError("Template not found")

    has_access = await repository.verify_category_belongs_to_tenant(
        db, default.category_id, principal.tenant_id,
    )
    if not has_access:
        raise NotFoundError("Template not found")

    deleted = await repository.delete_override(
        db, principal.tenant_id, template_id,
    )

    if deleted:
        await record_audit(
            db,
            tenant_id=principal.tenant_id,
            entity_type="config_template_override",
            entity_id=template_id,
            action="DELETE",
            changed_by_user_id=principal.id,
        )
        await db.commit()

    return await get_effective_template(db, principal, template_id)


async def preview_template(
    db: AsyncSession,
    principal: Principal,
    template_id: uuid.UUID,
    sample_data: dict[str, str],
) -> TemplatePreviewResponse:
    """Render the effective template with sample data for preview."""
    _require_tenant_admin(principal)

    effective = await get_effective_template(db, principal, template_id)

    # Build context from declared placeholders, using sample values as fallback
    context: dict[str, str] = {}
    for ph in effective.placeholders:
        key = ph.get("key", "")
        context[key] = sample_data.get(key, ph.get("sample_value", f"{{{{{key}}}}}"))

    rendered_subject = _render_placeholders(effective.subject, context) if effective.subject else None
    rendered_body = _render_placeholders(effective.body, context)

    return TemplatePreviewResponse(
        subject=rendered_subject,
        rendered_body=rendered_body,
    )


# ── Helpers ──────────────────────────────────────────────────────


def _validate_placeholders(default: object, body: str) -> None:
    """Ensure the override body still contains all required placeholders."""
    placeholders = getattr(default, "placeholders", [])
    if not isinstance(placeholders, list):
        return

    required_keys = {
        ph["key"]
        for ph in placeholders
        if isinstance(ph, dict) and ph.get("required") is True
    }

    body_keys = set(PLACEHOLDER_RE.findall(body))
    missing = required_keys - body_keys

    if missing:
        raise BusinessRuleError(
            f"Template body is missing required placeholders: {', '.join(sorted(missing))}"
        )


def _render_placeholders(text: str, context: dict[str, str]) -> str:
    """Replace ``{{key}}`` tokens with their values from context."""

    def _replacer(match: re.Match) -> str:
        key = match.group(1)
        return context.get(key, match.group(0))

    return PLACEHOLDER_RE.sub(_replacer, text)
