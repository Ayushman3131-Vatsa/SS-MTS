"""Database connection management.

Kept isolated from the rest of the app on purpose: today every tenant lives in
one Postgres database / one schema, distinguished only by the tenant_id
column (see Section 1 of the architecture doc). If that ever needs to move to
schema-per-tenant or database-per-tenant, `DatabaseSessionManager.session_for`
is the single seam to change — e.g. resolve a per-tenant engine/search_path
there — instead of touching every module/repository that calls `get_db`.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


class DatabaseSessionManager:
    def __init__(self, database_url: str):
        self._engine: AsyncEngine = create_async_engine(database_url, pool_pre_ping=True)
        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session_for(self, tenant_id: str | None = None) -> AsyncGenerator[AsyncSession, None]:
        """Yield a session scoped to a tenant.

        `tenant_id` is accepted (and currently unused) so callers already
        express tenant-scoped intent. Under the shared-schema model every
        tenant shares this one engine/session; a schema-per-tenant migration
        would key off `tenant_id` here to pick an engine or SET search_path.
        """
        async with self._sessionmaker() as session:
            try:
                yield session
            finally:
                await session.close()

    async def dispose(self) -> None:
        await self._engine.dispose()


_settings = get_settings()
db_manager = DatabaseSessionManager(_settings.database_url)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with db_manager.session_for() as session:
        yield session
