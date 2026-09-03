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
    ConfigTemplateCatalogItem,
    ConfigTemplateDetailResponse,
    ConfigTemplateListItem,
    TemplateOverrideRequest,
    TemplatePreviewResponse,
)

PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def _require_tenant_admin(principal: Principal) -> None:
    """Guard that only Tenant Admin can access configuration endpoints."""
    assigned = principal.roles or ((principal.role,) if principal.role else ())
    if principal.type != "user" or "Tenant Admin" not in assigned:
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


async def list_template_catalog(
    db: AsyncSession,
    principal: Principal,
) -> list[ConfigTemplateCatalogItem]:
    """Return every template available through the tenant's active licenses."""
    _require_tenant_admin(principal)
    rows = await repository.get_templates_for_tenant(db, principal.tenant_id)
    return [ConfigTemplateCatalogItem(**row) for row in rows]


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
    effective = repository.resolve_template_values(default, override)

    return ConfigTemplateDetailResponse(
        template_id=default.template_id,
        category_id=default.category_id,
        code=default.code,
        display_name=default.display_name,
        description=default.description,
        template_type=default.template_type,
        subject=effective.subject,
        body=effective.body,
        placeholders=default.placeholders if isinstance(default.placeholders, list) else [],
        metadata=effective.metadata,
        is_active=effective.is_active,
        sort_order=default.sort_order,
        is_customized=effective.is_customized,
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

    # Serialize by tenant/template even when this is the first override insert;
    # the subsequent row lock then protects merge-and-write updates. This keeps
    # two disjoint partial edits from overwriting one another's snapshots.
    await repository.lock_override_slot(
        db,
        principal.tenant_id,
        template_id,
    )
    existing_override = await repository.get_tenant_override(
        db,
        principal.tenant_id,
        template_id,
        for_update=True,
    )
    current = repository.resolve_template_values(default, existing_override)
    supplied_fields = payload.model_fields_set
    merged_subject = (
        payload.subject if "subject" in supplied_fields else current.subject
    )
    merged_body = payload.body if "body" in supplied_fields else current.body
    if merged_body is None:
        raise BusinessRuleError("Template body cannot be null")

    # Required placeholders may live in either field. Validate the complete
    # effective snapshot so a partial request cannot accidentally remove one.
    _validate_placeholders(default, merged_subject, merged_body)

    await repository.upsert_override(
        db,
        tenant_id=principal.tenant_id,
        template_id=template_id,
        user_id=principal.id,
        subject=merged_subject,
        body=merged_body,
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
        new_value=payload.model_dump(exclude_unset=True, mode="json"),
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

    await repository.lock_override_slot(
        db,
        principal.tenant_id,
        template_id,
    )
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
    # Also release the transaction-scoped serialization lock on a no-op reset.
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


def _validate_placeholders(
    default: object,
    subject: str | None,
    body: str,
) -> None:
    """Ensure the merged override still contains all required placeholders."""
    placeholders = getattr(default, "placeholders", [])
    if not isinstance(placeholders, list):
        return

    required_keys = {
        ph["key"]
        for ph in placeholders
        if isinstance(ph, dict) and ph.get("required") is True
    }

    content_keys = set(PLACEHOLDER_RE.findall(f"{subject or ''}\n{body}"))
    missing = required_keys - content_keys

    if missing:
        raise BusinessRuleError(
            "Template subject and body are missing required placeholders: "
            f"{', '.join(sorted(missing))}"
        )


def _render_placeholders(text: str, context: dict[str, str]) -> str:
    """Replace ``{{key}}`` tokens with their values from context."""

    def _replacer(match: re.Match) -> str:
        key = match.group(1)
        return context.get(key, match.group(0))

    return PLACEHOLDER_RE.sub(_replacer, text)
