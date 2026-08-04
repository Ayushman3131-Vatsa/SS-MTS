"""Database queries for the configuration/template system.

All tenant-scoped queries filter by tenant_id through the tenant_offerings join
so a tenant never sees categories or templates for offerings it has not licensed.
"""

import uuid

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_category import ConfigCategory
from app.models.config_template import ConfigTemplate
from app.models.offering import Offering
from app.models.tenant_config_override import TenantConfigOverride
from app.models.tenant_offering import TenantOffering


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
        .where(ConfigCategory.category_id == category_id)
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
    override_exists_subq = (
        select(func.count(TenantConfigOverride.override_id))
        .where(
            TenantConfigOverride.template_id == ConfigTemplate.template_id,
            TenantConfigOverride.tenant_id == tenant_id,
        )
        .correlate(ConfigTemplate)
        .scalar_subquery()
        .label("override_count")
    )

    stmt = (
        select(ConfigTemplate, override_exists_subq)
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
        templates.append(
            {
                "template_id": tmpl.template_id,
                "category_id": tmpl.category_id,
                "code": tmpl.code,
                "display_name": tmpl.display_name,
                "description": tmpl.description,
                "template_type": tmpl.template_type,
                "subject": tmpl.subject,
                "is_active": tmpl.is_active,
                "sort_order": tmpl.sort_order,
                "is_customized": (row.override_count or 0) > 0,
            }
        )
    return templates


async def get_template_by_id(
    db: AsyncSession,
    template_id: uuid.UUID,
) -> ConfigTemplate | None:
    return await db.get(ConfigTemplate, template_id)


async def get_tenant_override(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
) -> TenantConfigOverride | None:
    stmt = select(TenantConfigOverride).where(
        TenantConfigOverride.tenant_id == tenant_id,
        TenantConfigOverride.template_id == template_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_override(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    subject: str | None,
    body: str | None,
    metadata: dict | None,
    is_active: bool | None,
) -> TenantConfigOverride:
    """Create or update a tenant's template override."""
    existing = await get_tenant_override(db, tenant_id, template_id)

    if existing is not None:
        if subject is not None:
            existing.subject = subject
        if body is not None:
            existing.body = body
        if metadata is not None:
            existing.metadata_ = metadata
        if is_active is not None:
            existing.is_active = is_active
        existing.updated_by_user_id = user_id
        await db.flush()
        await db.refresh(existing)
        return existing

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
