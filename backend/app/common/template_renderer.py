import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.configurations import repository as configuration_repository

PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


@dataclass(frozen=True)
class RenderedTemplate:
    """The result of rendering a template for a tenant."""

    template_code: str
    template_type: str
    subject: str | None
    body: str
    metadata: dict = field(default_factory=dict)
    is_customized: bool = False


async def render_template(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    template_code: str,
    context: dict[str, str | object],
) -> RenderedTemplate:
    """Fetch and render a template for a tenant.

    1. Finds the default template in ``config_templates`` by code.
    2. Checks for a tenant-specific override in ``tenant_config_overrides``.
    3. Merges default + override values.
    4. Interpolates ``{{placeholder}}`` tokens using keys in ``context``.

    Args:
        db: Active AsyncSession.
        tenant_id: UUID of the tenant requesting the rendered template.
        template_code: Unique code of the template (e.g. 'welcome_email', 'task_assigned').
        context: Key-value dictionary matching the template's placeholder variables.

    Returns:
        RenderedTemplate containing the final subject, body, and metadata.

    Raises:
        NotFoundError: If no template exists with the given code for a
            currently entitled offering.
    """
    # 1. Look up the platform default through the tenant's current offering
    # entitlement. This prevents expired or unlicensed tenants from resolving
    # catalog templates by guessing their globally unique code.
    default = await configuration_repository.get_entitled_template_by_code(
        db,
        tenant_id,
        template_code,
    )

    if default is None:
        raise NotFoundError(f"Template with code '{template_code}' not found")

    # 2. Check if tenant has an override for this template
    override = await configuration_repository.get_tenant_override(
        db, tenant_id, default.template_id,
    )

    # 3. Determine effective subject, body, and metadata using the same
    # precedence as the tenant-facing configuration API.
    effective = configuration_repository.resolve_template_values(default, override)
    if not effective.is_active:
        raise NotFoundError(
            f"Template with code '{template_code}' is inactive for this tenant"
        )

    # Stringify context values
    string_context = {
        k: str(v) if v is not None else ""
        for k, v in context.items()
    }

    # 4. Interpolate placeholders
    rendered_subject = (
        _interpolate_placeholders(effective.subject, string_context)
        if effective.subject is not None
        else None
    )
    rendered_body = _interpolate_placeholders(effective.body, string_context)

    return RenderedTemplate(
        template_code=default.code,
        template_type=default.template_type,
        subject=rendered_subject,
        body=rendered_body,
        metadata=effective.metadata,
        is_customized=effective.is_customized,
    )


async def render_platform_template(
    db: AsyncSession,
    template_code: str,
    context: dict[str, str | object],
) -> RenderedTemplate:
    """Fetch and render a platform-scoped template without tenant overrides."""
    template = await configuration_repository.get_template_by_code(db, template_code)
    if template is None:
        raise NotFoundError(f"Platform template with code '{template_code}' not found")
    if not template.is_active:
        raise NotFoundError(f"Platform template with code '{template_code}' is inactive")

    string_context = {
        k: str(v) if v is not None else ""
        for k, v in context.items()
    }

    rendered_subject = (
        _interpolate_placeholders(template.subject, string_context)
        if template.subject is not None
        else None
    )
    rendered_body = _interpolate_placeholders(template.body, string_context)

    return RenderedTemplate(
        template_code=template.code,
        template_type=template.template_type,
        subject=rendered_subject,
        body=rendered_body,
        metadata=template.metadata_ or {},
        is_customized=False,
    )


def _interpolate_placeholders(text: str, context: dict[str, str]) -> str:
    """Replace {{placeholder}} tokens with values from context."""

    def _replacer(match: re.Match) -> str:
        key = match.group(1)
        # If the key exists in context, replace it; otherwise leave intact
        return context.get(key, match.group(0))

    return PLACEHOLDER_RE.sub(_replacer, text)
