from dataclasses import dataclass
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_category import ConfigCategory
from app.models.offering import Offering
from app.models.tenant_offering import TenantOffering


@dataclass(frozen=True)
class OfferingCatalogReadModel:
    offering_id: uuid.UUID
    code: str
    display_name: str
    description: str
    icon_key: str
    route_slug: str
    sort_order: int
    status: str
    tenant_entitlement_count: int
    configuration_category_count: int


def _usage_count_subqueries():
    entitlement_count = (
        select(func.count(TenantOffering.entitlement_id))
        .where(TenantOffering.offering_id == Offering.offering_id)
        .correlate(Offering)
        .scalar_subquery()
    )
    category_count = (
        select(func.count(ConfigCategory.category_id))
        .where(ConfigCategory.offering_id == Offering.offering_id)
        .correlate(Offering)
        .scalar_subquery()
    )
    return entitlement_count, category_count


async def list_catalog(db: AsyncSession) -> list[OfferingCatalogReadModel]:
    entitlement_count, category_count = _usage_count_subqueries()
    result = await db.execute(
        select(
            Offering.offering_id,
            Offering.code,
            Offering.display_name,
            Offering.description,
            Offering.icon_key,
            Offering.route_slug,
            Offering.sort_order,
            Offering.status,
            entitlement_count.label("tenant_entitlement_count"),
            category_count.label("configuration_category_count"),
        ).order_by(Offering.status.desc(), Offering.sort_order, Offering.display_name)
    )
    return [OfferingCatalogReadModel(**row) for row in result.mappings().all()]


async def get_catalog_item(
    db: AsyncSession, offering_id: uuid.UUID
) -> OfferingCatalogReadModel | None:
    entitlement_count, category_count = _usage_count_subqueries()
    row = (
        await db.execute(
            select(
                Offering.offering_id,
                Offering.code,
                Offering.display_name,
                Offering.description,
                Offering.icon_key,
                Offering.route_slug,
                Offering.sort_order,
                Offering.status,
                entitlement_count.label("tenant_entitlement_count"),
                category_count.label("configuration_category_count"),
            ).where(Offering.offering_id == offering_id)
        )
    ).mappings().one_or_none()
    return OfferingCatalogReadModel(**row) if row is not None else None
