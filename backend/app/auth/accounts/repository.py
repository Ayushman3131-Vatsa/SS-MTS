import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models.user_account import UserAccount


async def get_user(db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID) -> UserAccount | None:
    user = await db.get(UserAccount, user_id)
    if user is None or user.tenant_id != tenant_id:
        return None
    return user


async def get_user_by_email(db: AsyncSession, tenant_id: uuid.UUID, email: str) -> UserAccount | None:
    result = await db.execute(
        select(UserAccount).where(UserAccount.tenant_id == tenant_id, UserAccount.email == email)
    )
    return result.scalar_one_or_none()


async def list_users(db: AsyncSession, tenant_id: uuid.UUID) -> list[UserAccount]:
    result = await db.execute(select(UserAccount).where(UserAccount.tenant_id == tenant_id))
    return list(result.scalars().all())
