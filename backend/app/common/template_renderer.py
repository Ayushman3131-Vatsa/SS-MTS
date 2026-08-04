"""Template Rendering Engine.

Used by backend services (Core HR, Task Management, Notifications, etc.) to
render dynamic templates for a specific tenant and template code.

It automatically resolves whether the tenant has a customized override or uses
the platform default, then interpolates context variables into {{placeholders}}.
"""

import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.config_template import ConfigTemplate
from app.models.tenant_config_override import TenantConfigOverride

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
        NotFoundError: If no template exists with the given template_code.
    """
    # 1. Look up platform default template by code
    stmt_tmpl = select(ConfigTemplate).where(ConfigTemplate.code == template_code)
    res_tmpl = await db.execute(stmt_tmpl)
    default = res_tmpl.scalar_one_or_none()

    if default is None:
        raise NotFoundError(f"Template with code '{template_code}' not found")

    # 2. Check if tenant has an override for this template
    stmt_override = select(TenantConfigOverride).where(
        TenantConfigOverride.tenant_id == tenant_id,
        TenantConfigOverride.template_id == default.template_id,
    )
    res_override = await db.execute(stmt_override)
    override = res_override.scalar_one_or_none()

    # 3. Determine effective subject, body, and metadata
    if override is not None:
        raw_subject = override.subject if override.subject is not None else default.subject
        raw_body = override.body if override.body is not None else default.body
        effective_metadata = (
            {**(default.metadata_ or {}), **(override.metadata_ or {})}
            if override.metadata_ is not None
            else (default.metadata_ or {})
        )
        is_customized = True
    else:
        raw_subject = default.subject
        raw_body = default.body
        effective_metadata = default.metadata_ or {}
        is_customized = False

    # Stringify context values
    string_context = {
        k: str(v) if v is not None else ""
        for k, v in context.items()
    }

    # 4. Interpolate placeholders
    rendered_subject = (
        _interpolate_placeholders(raw_subject, string_context)
        if raw_subject is not None
        else None
    )
    rendered_body = _interpolate_placeholders(raw_body, string_context)

    return RenderedTemplate(
        template_code=default.code,
        template_type=default.template_type,
        subject=rendered_subject,
        body=rendered_body,
        metadata=effective_metadata,
        is_customized=is_customized,
    )


def _interpolate_placeholders(text: str, context: dict[str, str]) -> str:
    """Replace {{placeholder}} tokens with values from context."""

    def _replacer(match: re.Match) -> str:
        key = match.group(1)
        # If the key exists in context, replace it; otherwise leave intact
        return context.get(key, match.group(0))

    return PLACEHOLDER_RE.sub(_replacer, text)
