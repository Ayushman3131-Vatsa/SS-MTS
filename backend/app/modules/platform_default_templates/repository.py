from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy import and_, func, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_category import ConfigCategory
from app.models.config_template import ConfigTemplate
from app.models.offering import Offering
from app.models.tenant_config_override import TenantConfigOverride
from app.models.tenant_offering import TenantOffering


@dataclass(frozen=True)
class DefaultTemplateReadModel:
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
    type: str
    subject: str | None
    body: str
    placeholders: list[dict]
    sort_order: int
    is_active: bool
    version: int
    created_at: datetime
    updated_at: datetime
    inheriting_tenant_count: int
    customized_tenant_count: int


_CATEGORY_NAMES = {
    "EMAIL": "Email Templates",
    "LETTER": "Letter Templates",
    "NOTIFICATION": "Notification Templates",
    "OTHER": "Other Templates",
}
_CATEGORY_ICONS = {
    "EMAIL": "mail",
    "LETTER": "file-text",
    "NOTIFICATION": "bell",
    "OTHER": "file-text",
}
_CATEGORY_SORT_ORDERS = {
    "EMAIL": 10,
    "LETTER": 20,
    "NOTIFICATION": 30,
    "OTHER": 40,
}


def _active_entitlement_predicates() -> tuple:
    return (
        TenantOffering.status == "ACTIVE",
        TenantOffering.starts_at <= func.now(),
        (TenantOffering.ends_at.is_(None)) | (TenantOffering.ends_at > func.now()),
    )


def _usage_count_subqueries():
    eligible_tenant_count = (
        select(func.count(func.distinct(TenantOffering.tenant_id)))
        .where(
            TenantOffering.offering_id == ConfigCategory.offering_id,
            *_active_entitlement_predicates(),
        )
        .correlate(ConfigCategory)
        .scalar_subquery()
    )
    customized_tenant_count = (
        select(func.count(func.distinct(TenantConfigOverride.tenant_id)))
        .select_from(TenantConfigOverride)
        .join(
            TenantOffering,
            and_(
                TenantOffering.tenant_id == TenantConfigOverride.tenant_id,
                TenantOffering.offering_id == ConfigCategory.offering_id,
            ),
        )
        .where(
            TenantConfigOverride.template_id == ConfigTemplate.template_id,
            *_active_entitlement_predicates(),
        )
        .correlate(ConfigTemplate, ConfigCategory)
        .scalar_subquery()
    )
    return eligible_tenant_count, customized_tenant_count


def _read_statement():
    eligible_tenant_count, customized_tenant_count = _usage_count_subqueries()
    return (
        select(
            ConfigTemplate.template_id,
            Offering.offering_id,
            Offering.code.label("offering_code"),
            Offering.display_name.label("offering_name"),
            ConfigCategory.category_id,
            ConfigCategory.code.label("category_code"),
            ConfigCategory.display_name.label("category_name"),
            ConfigTemplate.code,
            ConfigTemplate.display_name.label("name"),
            ConfigTemplate.description,
            ConfigTemplate.template_type.label("type"),
            ConfigTemplate.subject,
            ConfigTemplate.body,
            ConfigTemplate.placeholders,
            ConfigTemplate.sort_order,
            ConfigTemplate.is_active,
            ConfigTemplate.version,
            ConfigTemplate.created_at,
            ConfigTemplate.updated_at,
            (eligible_tenant_count - customized_tenant_count).label(
                "inheriting_tenant_count"
            ),
            customized_tenant_count.label("customized_tenant_count"),
        )
        .join(
            ConfigCategory,
            ConfigCategory.category_id == ConfigTemplate.category_id,
        )
        .join(Offering, Offering.offering_id == ConfigCategory.offering_id)
    )


def _to_read_model(row) -> DefaultTemplateReadModel:
    data = dict(row)
    placeholders = data.get("placeholders") or []
    if not isinstance(placeholders, list):
        placeholders = []
    data["placeholders"] = placeholders
    inheriting = data.get("inheriting_tenant_count")
    customized = data.get("customized_tenant_count")
    data["inheriting_tenant_count"] = int(inheriting or 0)
    data["customized_tenant_count"] = int(customized or 0)
    return DefaultTemplateReadModel(**data)


async def list_for_offering(
    db: AsyncSession,
    offering_id: uuid.UUID,
) -> list[DefaultTemplateReadModel]:
    rows = (
        await db.execute(
            _read_statement()
            .where(Offering.offering_id == offering_id)
            .order_by(
                ConfigCategory.sort_order,
                ConfigTemplate.sort_order,
                ConfigTemplate.display_name,
            )
        )
    ).mappings().all()
    return [_to_read_model(row) for row in rows]


async def get_detail(
    db: AsyncSession,
    template_id: uuid.UUID,
) -> DefaultTemplateReadModel | None:
    row = (
        await db.execute(
            _read_statement().where(ConfigTemplate.template_id == template_id)
        )
    ).mappings().one_or_none()
    return _to_read_model(row) if row is not None else None


async def get_offering(
    db: AsyncSession,
    offering_id: uuid.UUID,
) -> Offering | None:
    return await db.get(Offering, offering_id)


async def get_or_create_typed_category(
    db: AsyncSession,
    offering: Offering,
    template_type: str,
) -> uuid.UUID:
    """Upsert the one category used by an offering/template-type pair."""
    category_name = _CATEGORY_NAMES[template_type]
    statement = (
        postgresql_insert(ConfigCategory)
        .values(
            category_id=uuid.uuid4(),
            offering_id=offering.offering_id,
            code=f"{offering.code.lower()}_{template_type.lower()}_templates",
            template_type=template_type,
            display_name=category_name,
            description=f"{category_name} for {offering.display_name}",
            icon_key=_CATEGORY_ICONS[template_type],
            sort_order=_CATEGORY_SORT_ORDERS[template_type],
            status="ACTIVE",
        )
        .on_conflict_do_update(
            constraint="uq_config_categories_offering_type",
            set_={"status": "ACTIVE", "updated_at": func.now()},
        )
        .returning(ConfigCategory.category_id)
    )
    category_id = (await db.execute(statement)).scalar_one()
    return category_id


async def update_if_version(
    db: AsyncSession,
    template_id: uuid.UUID,
    expected_version: int,
    values: dict[str, object],
) -> bool:
    result = await db.execute(
        update(ConfigTemplate)
        .where(
            ConfigTemplate.template_id == template_id,
            ConfigTemplate.version == expected_version,
        )
        .values(
            **values,
            version=ConfigTemplate.version + 1,
            updated_at=func.now(),
        )
        .returning(ConfigTemplate.template_id)
    )
    return result.scalar_one_or_none() is not None
