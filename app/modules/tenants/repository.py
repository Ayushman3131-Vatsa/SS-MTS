import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant


async def get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    return await db.get(Tenant, tenant_id)


async def list_tenants(db: AsyncSession) -> list[Tenant]:
    result = await db.execute(select(Tenant))
    return list(result.scalars().all())
