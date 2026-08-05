"""Shared async PostgreSQL fixtures for the backend test suite.

The fixtures use one transaction per test and roll it back, so the configured
development database is never left with test rows. Set TEST_DATABASE_URL when
running the suite against an isolated test database.
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models.platform_admin import PlatformAdmin
from app.models.tenant import Tenant
from app.models.user import User


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    database_url = os.getenv("TEST_DATABASE_URL") or get_settings().database_url
    engine = create_async_engine(database_url, poolclass=NullPool)
    try:
        try:
            connection = await engine.connect()
        except SQLAlchemyError as exc:
            pytest.skip(f"PostgreSQL test database is unavailable: {exc}")

        try:
            transaction = await connection.begin()
            session_factory = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
            async with session_factory() as session:
                yield session
            await transaction.rollback()
        finally:
            await connection.close()
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    admin_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    admin = PlatformAdmin(
        admin_id=admin_id,
        name="Test Platform Admin",
        email=f"admin-{admin_id.hex}@example.test",
        password_hash="test-only",
    )
    tenant = Tenant(
        tenant_id=tenant_id,
        org_name="Configuration Test Tenant",
        tenant_code=f"TEST_{tenant_id.hex[:8].upper()}",
        workspace_slug=f"test-{tenant_id.hex[:12]}",
        subscription_plan="Free",
        status="ACTIVE",
        created_by_admin_id=admin_id,
    )
    user = User(
        tenant_id=tenant_id,
        user_id=uuid.uuid4(),
        name="Configuration Test User",
        email=f"user-{tenant_id.hex}@example.test",
        password_hash="test-only",
        role="Tenant Admin",
        status="Active",
    )
    db_session.add_all([admin, tenant, user])
    await db_session.flush()
    return user
