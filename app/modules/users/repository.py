import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> User | None:
    return await db.get(User, {"tenant_id": tenant_id, "user_id": user_id})


async def get_user_by_email(db: AsyncSession, tenant_id: uuid.UUID, email: str) -> User | None:
    result = await db.execute(select(User).where(User.tenant_id == tenant_id, User.email == email))
    return result.scalar_one_or_none()


async def list_users(db: AsyncSession, tenant_id: uuid.UUID) -> list[User]:
    result = await db.execute(select(User).where(User.tenant_id == tenant_id))
    return list(result.scalars().all())
