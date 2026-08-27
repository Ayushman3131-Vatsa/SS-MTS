from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models.page import Page
from app.auth.models.platform_default_role import PlatformDefaultRole
from app.auth.models.platform_default_role_page_access import PlatformDefaultRolePageAccess
from app.tenant_management.models.offering import Offering


@dataclass(frozen=True)
class DefaultRoleReadModel:
    role_id: uuid.UUID
    role_code: str
    role_name: str
    description: str | None
    offering_id: uuid.UUID | None
    offering_code: str | None
    offering_name: str | None
    module_scope: str
    is_system: bool
    is_active: bool
    page_count: int
    modify_count: int
    view_count: int
    none_count: int
    version: int
    created_at: datetime
    updated_at: datetime


def _summary_subqueries():
    page_count = (
        select(func.count(PlatformDefaultRolePageAccess.id))
        .where(PlatformDefaultRolePageAccess.role_id == PlatformDefaultRole.id)
        .correlate(PlatformDefaultRole)
        .scalar_subquery()
    )
    modify_count = (
        select(func.count(PlatformDefaultRolePageAccess.id))
        .where(
            PlatformDefaultRolePageAccess.role_id == PlatformDefaultRole.id,
            PlatformDefaultRolePageAccess.access_level == "modify",
        )
        .correlate(PlatformDefaultRole)
        .scalar_subquery()
    )
    view_count = (
        select(func.count(PlatformDefaultRolePageAccess.id))
        .where(
            PlatformDefaultRolePageAccess.role_id == PlatformDefaultRole.id,
            PlatformDefaultRolePageAccess.access_level == "view",
        )
        .correlate(PlatformDefaultRole)
        .scalar_subquery()
    )
    none_count = (
        select(func.count(PlatformDefaultRolePageAccess.id))
        .where(
            PlatformDefaultRolePageAccess.role_id == PlatformDefaultRole.id,
            PlatformDefaultRolePageAccess.access_level == "none",
        )
        .correlate(PlatformDefaultRole)
        .scalar_subquery()
    )
    return page_count, modify_count, view_count, none_count


def _row_to_read_model(row: tuple) -> DefaultRoleReadModel:
    role, offering, page_count, modify_count, view_count, none_count = row
    return DefaultRoleReadModel(
        role_id=role.id,
        role_code=role.role_code,
        role_name=role.role_name,
        description=role.description,
        offering_id=role.offering_id,
        offering_code=offering.code if offering else None,
        offering_name=offering.display_name if offering else None,
        module_scope=role.module_scope,
        is_system=role.is_system,
        is_active=role.is_active,
        page_count=int(page_count or 0),
        modify_count=int(modify_count or 0),
        view_count=int(view_count or 0),
        none_count=int(none_count or 0),
        version=role.version,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


def _base_query():
    page_count, modify_count, view_count, none_count = _summary_subqueries()
    return (
        select(
            PlatformDefaultRole,
            Offering,
            page_count,
            modify_count,
            view_count,
            none_count,
        )
        .outerjoin(Offering, Offering.offering_id == PlatformDefaultRole.offering_id)
        .order_by(PlatformDefaultRole.module_scope, PlatformDefaultRole.role_name)
    )


async def get_offering(db: AsyncSession, offering_id: uuid.UUID) -> Offering | None:
    return await db.get(Offering, offering_id)


async def list_roles(
    db: AsyncSession,
    *,
    offering_id: uuid.UUID | None = None,
    core_only: bool = False,
) -> list[DefaultRoleReadModel]:
    query = _base_query()
    if core_only:
        query = query.where(PlatformDefaultRole.offering_id.is_(None))
    elif offering_id is not None:
        query = query.where(PlatformDefaultRole.offering_id == offering_id)
    result = await db.execute(query)
    return [_row_to_read_model(row) for row in result.all()]


async def get_role(db: AsyncSession, role_id: uuid.UUID) -> DefaultRoleReadModel | None:
    result = await db.execute(_base_query().where(PlatformDefaultRole.id == role_id))
    row = result.first()
    return _row_to_read_model(row) if row else None


async def get_role_model(db: AsyncSession, role_id: uuid.UUID) -> PlatformDefaultRole | None:
    return await db.get(PlatformDefaultRole, role_id)


async def list_access_by_role(
    db: AsyncSession, role_id: uuid.UUID
) -> list[PlatformDefaultRolePageAccess]:
    result = await db.execute(
        select(PlatformDefaultRolePageAccess).where(PlatformDefaultRolePageAccess.role_id == role_id)
    )
    return list(result.scalars().all())
