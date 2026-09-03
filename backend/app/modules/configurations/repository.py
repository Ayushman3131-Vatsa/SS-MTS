"""Database queries for the configuration/template system.

All tenant-scoped queries filter by tenant_id through the tenant_offerings join
so a tenant never sees categories or templates for offerings it has not licensed.
"""

from dataclasses import dataclass
import hashlib
import uuid

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_category import ConfigCategory
from app.models.config_template import ConfigTemplate
from app.models.offering import Offering
from app.models.tenant_config_override import TenantConfigOverride
from app.models.tenant_offering import TenantOffering


@dataclass(frozen=True)
class EffectiveTemplateValues:
    """Tenant-visible values after applying an optional override."""

    subject: str | None
    body: str
    metadata: dict
    is_active: bool
    is_customized: bool


def resolve_template_values(
    default: ConfigTemplate,
    override: TenantConfigOverride | None,
) -> EffectiveTemplateValues:
    """Apply the shared default/override precedence used by API and runtime reads."""
    if override is None:
        return EffectiveTemplateValues(
            subject=default.subject,
            body=default.body,
            metadata=default.metadata_ or {},
            is_active=default.is_active,
            is_customized=False,
        )

    return EffectiveTemplateValues(
        # The existence of an override row means the tenant owns a complete
        # subject/body snapshot. In particular, a NULL subject is an explicit
        # "no subject" value and must not begin inheriting a future default.
        subject=override.subject,
        body=override.body,
        metadata=(
            {**(default.metadata_ or {}), **(override.metadata_ or {})}
            if override.metadata_ is not None
            else (default.metadata_ or {})
        ),
        is_active=override.is_active,
        is_customized=True,
    )


async def get_categories_for_tenant(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> list[dict]:
    """Return categories whose offering is licensed to this tenant.

    Each result dict contains category columns plus the parent offering's
    ``code`` and ``display_name`` for the UI tab labels, and a count of
    active templates in the category.
    """
    template_count_subq = (
        select(func.count(ConfigTemplate.template_id))
        .where(
            ConfigTemplate.category_id == ConfigCategory.category_id,
            ConfigTemplate.is_active.is_(True),
        )
        .correlate(ConfigCategory)
        .scalar_subquery()
        .label("template_count")
    )

    stmt = (
        select(
            ConfigCategory,
            Offering.code.label("offering_code"),
            Offering.display_name.label("offering_display_name"),
            template_count_subq,
        )
        .join(Offering, Offering.offering_id == ConfigCategory.offering_id)
        .join(
            TenantOffering,
            (TenantOffering.offering_id == Offering.offering_id)
            & (TenantOffering.tenant_id == tenant_id),
        )
        .where(ConfigCategory.status == "ACTIVE")
        .where(
            TenantOffering.status == "ACTIVE",
            TenantOffering.starts_at <= func.now(),
            or_(TenantOffering.ends_at.is_(None), TenantOffering.ends_at > func.now()),
        )
        .order_by(ConfigCategory.sort_order, ConfigCategory.display_name)
    )
    result = await db.execute(stmt)
    rows = result.all()

    categories = []
    for row in rows:
        category = row[0]
        categories.append(
            {
                "category_id": category.category_id,
                "offering_id": category.offering_id,
                "offering_code": row.offering_code,
                "offering_display_name": row.offering_display_name,
                "code": category.code,
                "display_name": category.display_name,
                "description": category.description,
                "icon_key": category.icon_key,
                "sort_order": category.sort_order,
                "status": category.status,
                "template_count": row.template_count or 0,
            }
        )
    return categories


async def get_category_by_id(
    db: AsyncSession,
    category_id: uuid.UUID,
) -> ConfigCategory | None:
    return await db.get(ConfigCategory, category_id)


async def verify_category_belongs_to_tenant(
    db: AsyncSession,
    category_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> bool:
    """Check that the category's offering is licensed to this tenant."""
    stmt = (
        select(func.count())
        .select_from(ConfigCategory)
        .join(Offering, Offering.offering_id == ConfigCategory.offering_id)
        .join(
            TenantOffering,
            (TenantOffering.offering_id == Offering.offering_id)
            & (TenantOffering.tenant_id == tenant_id),
        )
        .where(
            ConfigCategory.category_id == category_id,
            TenantOffering.status == "ACTIVE",
            TenantOffering.starts_at <= func.now(),
            or_(TenantOffering.ends_at.is_(None), TenantOffering.ends_at > func.now()),
        )
    )
    result = await db.execute(stmt)
    return (result.scalar() or 0) > 0


async def get_templates_by_category(
    db: AsyncSession,
    category_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[dict]:
    """Return all active templates in a category with override status.

    Each dict includes the template fields plus ``is_customized`` (bool)
    indicating whether the tenant has an override row.
    """
    stmt = (
        select(ConfigTemplate, TenantConfigOverride)
        .outerjoin(
            TenantConfigOverride,
            (TenantConfigOverride.template_id == ConfigTemplate.template_id)
            & (TenantConfigOverride.tenant_id == tenant_id),
        )
        .where(
            ConfigTemplate.category_id == category_id,
            ConfigTemplate.is_active.is_(True),
        )
        .order_by(ConfigTemplate.sort_order, ConfigTemplate.display_name)
    )
    result = await db.execute(stmt)
    rows = result.all()

    templates = []
    for row in rows:
        tmpl = row[0]
        effective = resolve_template_values(tmpl, row[1])
        templates.append(
            {
                "template_id": tmpl.template_id,
                "category_id": tmpl.category_id,
                "code": tmpl.code,
                "display_name": tmpl.display_name,
                "description": tmpl.description,
                "template_type": tmpl.template_type,
                "subject": effective.subject,
                "is_active": effective.is_active,
                "sort_order": tmpl.sort_order,
                "is_customized": effective.is_customized,
            }
        )
    return templates


async def get_template_by_id(
    db: AsyncSession,
    template_id: uuid.UUID,
) -> ConfigTemplate | None:
    return await db.get(ConfigTemplate, template_id)


async def get_entitled_template_by_code(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    template_code: str,
) -> ConfigTemplate | None:
    """Resolve a runtime template only through a current active entitlement."""
    stmt = (
        select(ConfigTemplate)
        .join(
            ConfigCategory,
            ConfigCategory.category_id == ConfigTemplate.category_id,
        )
        .join(
            TenantOffering,
            TenantOffering.offering_id == ConfigCategory.offering_id,
        )
        .where(
            ConfigTemplate.code == template_code,
            ConfigTemplate.is_active.is_(True),
            ConfigCategory.status == "ACTIVE",
            TenantOffering.tenant_id == tenant_id,
            TenantOffering.status == "ACTIVE",
            TenantOffering.starts_at <= func.now(),
            or_(TenantOffering.ends_at.is_(None), TenantOffering.ends_at > func.now()),
        )
    )
    result = await db.execute(stmt)
    return result.scalars().unique().one_or_none()


async def get_template_by_code(
    db: AsyncSession,
    template_code: str,
) -> ConfigTemplate | None:
    """Fetch any active template by code (for platform-level notifications)."""
    stmt = select(ConfigTemplate).where(
        ConfigTemplate.code == template_code,
        ConfigTemplate.is_active.is_(True),
    )
    result = await db.execute(stmt)
    return result.scalars().unique().one_or_none()


async def get_tenant_override(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> TenantConfigOverride | None:
    stmt = select(TenantConfigOverride).where(
        TenantConfigOverride.tenant_id == tenant_id,
        TenantConfigOverride.template_id == template_id,
    )
    if for_update:
        stmt = stmt.with_for_update()
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def lock_override_slot(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
) -> None:
    """Serialize writes even before the tenant/template override row exists."""
    digest = hashlib.blake2b(
        f"{tenant_id}:{template_id}".encode(),
        digest_size=8,
    ).digest()
    lock_key = int.from_bytes(digest, byteorder="big", signed=True)
    await db.execute(select(func.pg_advisory_xact_lock(lock_key)))


async def upsert_override(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    subject: str | None,
    body: str,
    metadata: dict | None,
    is_active: bool | None,
) -> TenantConfigOverride:
    """Create or update a tenant's template override."""
    existing = await get_tenant_override(
        db,
        tenant_id,
        template_id,
        for_update=True,
    )

    if existing is not None:
        # Service callers pass the fully merged content snapshot so omitted
        # request fields retain their current effective value while explicit
        # NULL subjects remain meaningful.
        existing.subject = subject
        existing.body = body
        if metadata is not None:
            existing.metadata_ = metadata
        if is_active is not None:
            existing.is_active = is_active
        existing.updated_by_user_id = user_id
        await db.flush()
        await db.refresh(existing)
        return existing

    default = await get_template_by_id(db, template_id)
    if default is None:
        raise ValueError("Cannot create an override for a missing template")

    override = TenantConfigOverride(
        tenant_id=tenant_id,
        template_id=template_id,
        subject=subject,
        body=body,
        metadata_=metadata,
        is_active=is_active if is_active is not None else True,
        updated_by_user_id=user_id,
    )
    db.add(override)
    await db.flush()
    await db.refresh(override)
    return override


async def delete_override(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
) -> bool:
    """Delete a tenant's override, resetting to platform default.

    Returns True if an override was actually deleted.
    """
    stmt = delete(TenantConfigOverride).where(
        TenantConfigOverride.tenant_id == tenant_id,
        TenantConfigOverride.template_id == template_id,
    )
    result = await db.execute(stmt)
    return result.rowcount > 0
