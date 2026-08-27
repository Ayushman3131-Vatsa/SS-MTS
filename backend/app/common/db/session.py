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
import uuid

from fastapi import Request
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from app.common.config import get_settings


# Only the HTTP dependency in this module can elevate an ordinary session to
# platform-wide RLS scope, and it does so from middleware-verified claims.
VERIFIED_PLATFORM_SCOPE = object()
_VERIFIED_PLATFORM_SCOPE = VERIFIED_PLATFORM_SCOPE


@event.listens_for(Session, "after_begin")
def _apply_rls_context(session: Session, transaction, connection) -> None:
    """Reapply transaction-local RLS context after every commit/rollback.

    AsyncSession exposes its underlying synchronous Session to SQLAlchemy
    events. Executing through the event connection participates in the newly
    opened transaction and avoids session-level settings leaking through the
    connection pool.
    """
    principal_type = session.info.get("rls_principal_type")
    if principal_type is None:
        return
    connection.execute(
        text(
            "SELECT "
            "set_config('app.principal_type', :principal_type, true), "
            "set_config('app.tenant_id', :tenant_id, true)"
        ),
        {
            "principal_type": principal_type,
            "tenant_id": session.info.get("rls_tenant_id", ""),
        },
    )


class DatabaseSessionManager:
    def __init__(self, database_url: str):
        self._engine: AsyncEngine = create_async_engine(database_url, pool_pre_ping=True)
        self._sessionmaker = async_sessionmaker(
            bind=self._engine,
            autoflush=False,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def session_for(
        self,
        tenant_id: str | uuid.UUID | None = None,
        *,
        principal_type: str | None = None,
        _platform_scope: object | None = None,
    ) -> AsyncGenerator[AsyncSession, None]:
        """Yield a session scoped to a tenant.

        Task Management tables use PostgreSQL RLS. Context is transaction
        local, so pooled connections cannot retain a previous request's
        tenant. Sessions with no verified principal receive no RLS context and
        therefore cannot see offering-owned rows.
        """
        async with self._sessionmaker() as session:
            try:
                if principal_type is not None:
                    if principal_type not in {"admin", "platform_admin", "user"}:
                        raise ValueError("Unknown RLS principal type")
                    normalized_type = "admin" if principal_type in {"admin", "platform_admin"} else "user"
                    if (
                        normalized_type == "admin"
                        and _platform_scope is not _VERIFIED_PLATFORM_SCOPE
                    ):
                        raise ValueError(
                            "Platform RLS scope requires a verified authentication context"
                        )
                    normalized_tenant = ""
                    if normalized_type == "user" and tenant_id is not None:
                        normalized_tenant = str(uuid.UUID(str(tenant_id)))
                    session.sync_session.info["rls_principal_type"] = normalized_type
                    session.sync_session.info["rls_tenant_id"] = normalized_tenant
                yield session
            finally:
                await session.close()

    async def dispose(self) -> None:
        await self._engine.dispose()


_settings = get_settings()
db_manager = DatabaseSessionManager(_settings.database_url)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    claims = getattr(request.state, "jwt_claims", None)
    principal_type = claims.get("type") if isinstance(claims, dict) else None
    tenant_id = claims.get("tenant_id") if isinstance(claims, dict) else None
    async with db_manager.session_for(
        tenant_id=tenant_id,
        principal_type=principal_type,
        _platform_scope=_VERIFIED_PLATFORM_SCOPE,
    ) as session:
        yield session
