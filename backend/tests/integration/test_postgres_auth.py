"""Destructive-safe PostgreSQL and API integration coverage for authentication.

The only database this module mutates is a random database whose name must
match ``mt_auth_test_<32 lowercase hex characters>``. The source URL's
database is never opened: its server and credentials are used to connect to
the conventional ``postgres`` maintenance database instead.
"""

from __future__ import annotations

import asyncio
import hashlib
import http.client
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from dataclasses import dataclass
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any

from alembic.config import Config
from alembic.script import ScriptDirectory
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SAFE_DATABASE_NAME = re.compile(r"^mt_auth_test_[0-9a-f]{32}$")

PLATFORM_ADMIN_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
LEGACY_ADMIN_ID = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
THROTTLE_ADMIN_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
TENANT_ONE_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
TENANT_TWO_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
SHORT_ORG_TENANT_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
TENANT_ONE_USER_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")
TENANT_TWO_USER_ID = uuid.UUID("55555555-5555-4555-8555-555555555555")

PLATFORM_EMAIL = "operator@example.com"
PLATFORM_PASSWORD = "Nimbus!Harbor72"
LEGACY_EMAIL = "legacy@example.com"
LEGACY_PASSWORD = "Legacy!Harbor72"
THROTTLE_EMAIL = "throttle@example.com"
THROTTLE_PASSWORD = "Throttle!Safe42"
SHARED_MEMBER_EMAIL = "member@example.com"
SECOND_MEMBER_EMAIL = "second-member@example.com"
SHARED_MEMBER_PASSWORD = "Orbit!Sparrow42"

_argon2_context = CryptContext(
    schemes=["argon2"],
    argon2__type="ID",
    argon2__memory_cost=65536,
    argon2__time_cost=3,
    argon2__parallelism=4,
)
_bcrypt_context = CryptContext(schemes=["bcrypt"])


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    def header(self, name: str) -> str | None:
        expected = name.casefold()
        return next(
            (value for key, value in self.headers if key.casefold() == expected),
            None,
        )

    def headers_for(self, name: str) -> list[str]:
        expected = name.casefold()
        return [
            value
            for key, value in self.headers
            if key.casefold() == expected
        ]


def _contains_insufficient_privilege(exc: BaseException) -> bool:
    """Find asyncpg's privilege exception through SQLAlchemy wrappers."""

    pending: list[BaseException] = [exc]
    visited: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        if current.__class__.__name__ == "InsufficientPrivilegeError":
            return True
        for nested in (
            getattr(current, "orig", None),
            current.__cause__,
            current.__context__,
        ):
            if isinstance(nested, BaseException):
                pending.append(nested)
    return False


class SecureAuthPostgresIntegrationTests(unittest.TestCase):
    """One disposable PostgreSQL database shared by the ordered scenarios."""

    source_url: URL
    admin_url: URL
    database_url: URL
    database_name: str
    server_process: subprocess.Popen[bytes]
    server_log: Any
    server_port: int
    head_revision: str

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        raw_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if not raw_url:
            raise unittest.SkipTest(
                "Set TEST_DATABASE_URL to a PostgreSQL URL for a role with "
                "CREATEDB (DATABASE_URL is also accepted)."
            )

        cls.source_url = make_url(raw_url)
        if not cls.source_url.drivername.startswith("postgresql"):
            raise unittest.SkipTest(
                "TEST_DATABASE_URL/DATABASE_URL must use PostgreSQL."
            )

        cls.database_name = f"mt_auth_test_{uuid.uuid4().hex}"
        cls._assert_safe_database_name(cls.database_name)
        cls.admin_url = cls.source_url.set(
            drivername="postgresql+asyncpg",
            database="postgres",
        )
        cls.database_url = cls.source_url.set(
            drivername="postgresql+asyncpg",
            database=cls.database_name,
        )

        try:
            cls._run_async(cls._create_database())
        except DBAPIError as exc:
            if _contains_insufficient_privilege(exc):
                raise unittest.SkipTest(
                    "The PostgreSQL role cannot CREATE DATABASE. Grant CREATEDB "
                    "to the test role or use a dedicated integration-test role."
                ) from exc
            raise

        # Class cleanups run even when the remaining setUpClass work fails.
        cls.addClassCleanup(cls._drop_database_safely)

        cls._run_alembic("0001")
        cls._run_async(cls._seed_legacy_revision())
        cls._run_alembic("0002")
        cls._run_async(cls._seed_revision_0002_edge_cases())
        cls._run_alembic("0018")
        cls._run_async(cls._seed_revision_0018_contacts())
        alembic_config = Config(str(REPOSITORY_ROOT / "alembic.ini"))
        cls.head_revision = ScriptDirectory.from_config(
            alembic_config
        ).get_current_head()
        cls._run_alembic("head")
        cls._assert_database_identity()

        cls._start_server()
        cls.addClassCleanup(cls._stop_server)

    @classmethod
    def _assert_safe_database_name(cls, name: str) -> None:
        if SAFE_DATABASE_NAME.fullmatch(name) is None:
            raise RuntimeError(
                "Refusing database operation: integration database name does "
                "not match the exact mt_auth_test_<32 hex> safety pattern."
            )

    @classmethod
    def _render_database_url(cls) -> str:
        return cls.database_url.render_as_string(hide_password=False)

    @classmethod
    def _test_environment(cls) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "DATABASE_URL": cls._render_database_url(),
                "ENVIRONMENT": "testing",
                "JWT_SECRET_KEY": "integration-only-jwt-secret-key-000000000000",
                "BROWSER_SESSION_EXPIRE_MINUTES": "60",
                "AUTH_RATE_LIMIT_WINDOW_MINUTES": "15",
                "AUTH_ACCOUNT_FAILURE_LIMIT": "5",
                "AUTH_IP_FAILURE_LIMIT": "20",
                "AUTH_LOCKOUT_MINUTES": "15",
            }
        )
        return environment

    @staticmethod
    def _run_async(coroutine):
        return asyncio.run(coroutine)

    @classmethod
    async def _create_database(cls) -> None:
        cls._assert_safe_database_name(cls.database_name)
        engine = create_async_engine(
            cls.admin_url,
            isolation_level="AUTOCOMMIT",
            poolclass=NullPool,
        )
        try:
            async with engine.connect() as connection:
                await connection.exec_driver_sql(
                    f'CREATE DATABASE "{cls.database_name}"'
                )
        finally:
            await engine.dispose()

    @classmethod
    def _drop_database_safely(cls) -> None:
        cls._assert_safe_database_name(cls.database_name)

        async def drop() -> None:
            engine = create_async_engine(
                cls.admin_url,
                isolation_level="AUTOCOMMIT",
                poolclass=NullPool,
            )
            try:
                async with engine.connect() as connection:
                    await connection.execute(
                        text(
                            "SELECT pg_terminate_backend(pid) "
                            "FROM pg_stat_activity "
                            "WHERE datname = :database_name "
                            "AND pid <> pg_backend_pid()"
                        ),
                        {"database_name": cls.database_name},
                    )
                    cls._assert_safe_database_name(cls.database_name)
                    await connection.exec_driver_sql(
                        f'DROP DATABASE "{cls.database_name}"'
                    )
            finally:
                await engine.dispose()

        cls._run_async(drop())

    @classmethod
    def _run_alembic(cls, target: str) -> None:
        completed = cls._invoke_alembic("upgrade", target)
        if completed.returncode != 0:
            raise RuntimeError(
                f"Alembic upgrade {target!r} failed in the disposable "
                f"database:\n{completed.stdout}"
            )

    @classmethod
    def _invoke_alembic(
        cls,
        command: str,
        target: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", command, target],
            cwd=REPOSITORY_ROOT,
            env=cls._test_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
            check=False,
        )

    @classmethod
    def _run_alembic_downgrade(cls, target: str) -> None:
        completed = cls._invoke_alembic("downgrade", target)
        if completed.returncode != 0:
            raise RuntimeError(
                f"Alembic downgrade {target!r} failed in the disposable "
                f"database:\n{completed.stdout}"
            )

    @classmethod
    async def _seed_legacy_revision(cls) -> None:
        """Insert deterministic revision-0001 data before the 0002 backfill."""

        argon2_hash = _argon2_context.hash(PLATFORM_PASSWORD)
        legacy_hash = _bcrypt_context.hash(LEGACY_PASSWORD)
        throttle_hash = _argon2_context.hash(THROTTLE_PASSWORD)
        member_hash = _argon2_context.hash(SHARED_MEMBER_PASSWORD)

        engine = create_async_engine(cls.database_url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                current_database = await connection.scalar(
                    text("SELECT current_database()")
                )
                if current_database != cls.database_name:
                    raise RuntimeError(
                        "Refusing seed: connection is not using the exact "
                        "disposable integration database."
                    )

                await connection.execute(
                    text(
                        """
                        INSERT INTO platform_admins
                            (admin_id, name, email, password_hash)
                        VALUES
                            (:platform_id, 'Test Operator',
                             ' Operator@Example.COM ', :platform_hash),
                            (:legacy_id, 'Legacy Operator',
                             :legacy_email, :legacy_hash),
                            (:throttle_id, 'Throttle Operator',
                             :throttle_email, :throttle_hash)
                        """
                    ),
                    {
                        "platform_id": PLATFORM_ADMIN_ID,
                        "platform_hash": argon2_hash,
                        "legacy_id": LEGACY_ADMIN_ID,
                        "legacy_email": LEGACY_EMAIL,
                        "legacy_hash": legacy_hash,
                        "throttle_id": THROTTLE_ADMIN_ID,
                        "throttle_email": THROTTLE_EMAIL,
                        "throttle_hash": throttle_hash,
                    },
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO tenants
                            (tenant_id, org_name, created_by_admin_id)
                        VALUES
                            (:tenant_one, 'Acme Labs!', :platform_id),
                            (:tenant_two, 'Acme Labs', :platform_id),
                            (:tenant_three, 'X', :platform_id)
                        """
                    ),
                    {
                        "tenant_one": TENANT_ONE_ID,
                        "tenant_two": TENANT_TWO_ID,
                        "tenant_three": SHORT_ORG_TENANT_ID,
                        "platform_id": PLATFORM_ADMIN_ID,
                    },
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO users
                            (tenant_id, user_id, name, email, password_hash,
                             role, status)
                        VALUES
                            (:tenant_one, :user_one, 'Shared Member',
                             ' Member@Example.COM ', :member_hash,
                             'Tenant Admin', 'Active'),
                            (:tenant_two, :user_two, 'Shared Member',
                             :second_member_email, :member_hash,
                             'Employee', 'Active')
                        """
                    ),
                    {
                        "tenant_one": TENANT_ONE_ID,
                        "user_one": TENANT_ONE_USER_ID,
                        "tenant_two": TENANT_TWO_ID,
                        "user_two": TENANT_TWO_USER_ID,
                        "second_member_email": SECOND_MEMBER_EMAIL,
                        "member_hash": member_hash,
                    },
                )
        finally:
            await engine.dispose()

    @classmethod
    async def _seed_revision_0002_edge_cases(cls) -> None:
        """Prove the following migration canonicalizes legacy separators."""

        engine = create_async_engine(cls.database_url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        UPDATE tenants
                        SET workspace_slug = 'x--org'
                        WHERE tenant_id = :tenant_id
                        """
                    ),
                    {"tenant_id": SHORT_ORG_TENANT_ID},
                )
        finally:
            await engine.dispose()

    @classmethod
    async def _seed_revision_0018_contacts(cls) -> None:
        """Prepare legacy tenants for the 0019 primary-contact preflight."""

        engine = create_async_engine(cls.database_url, poolclass=NullPool)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        UPDATE tenants
                        SET contact_name = CASE tenant_id
                                WHEN :tenant_one THEN 'Shared Member'
                                WHEN :tenant_two THEN 'Second Member'
                                ELSE 'Short Organization Contact'
                            END,
                            contact_email = CASE tenant_id
                                WHEN :tenant_one THEN :member_email
                                WHEN :tenant_two THEN :second_member_email
                                ELSE 'short-contact@example.com'
                            END
                        """
                    ),
                    {
                        "tenant_one": TENANT_ONE_ID,
                        "tenant_two": TENANT_TWO_ID,
                        "member_email": SHARED_MEMBER_EMAIL,
                        "second_member_email": SECOND_MEMBER_EMAIL,
                    },
                )
        finally:
            await engine.dispose()

    @classmethod
    def _assert_database_identity(cls) -> None:
        actual = cls._db_scalar("SELECT current_database()")
        if actual != cls.database_name:
            raise RuntimeError(
                "Refusing integration tests: SQL connection is not using the "
                "exact disposable integration database."
            )

    @classmethod
    def _start_server(cls) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            cls.server_port = int(probe.getsockname()[1])

        cls.server_log = tempfile.TemporaryFile()
        cls.server_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(cls.server_port),
                "--log-level",
                "warning",
            ],
            cwd=REPOSITORY_ROOT,
            env=cls._test_environment(),
            stdout=cls.server_log,
            stderr=subprocess.STDOUT,
        )

        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if cls.server_process.poll() is not None:
                break
            try:
                if cls._request("GET", "/health").status == 200:
                    return
            except OSError:
                pass
            time.sleep(0.1)

        cls.server_log.seek(0)
        output = cls.server_log.read().decode("utf-8", errors="replace")
        cls._stop_server()
        raise RuntimeError(f"Uvicorn did not become ready:\n{output}")

    @classmethod
    def _stop_server(cls) -> None:
        process = getattr(cls, "server_process", None)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        log = getattr(cls, "server_log", None)
        if log is not None and not log.closed:
            log.close()

    @classmethod
    def _request(
        cls,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> HttpResponse:
        body = (
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
            if payload is not None
            else None
        )
        request_headers = dict(headers or {})
        if body is not None:
            request_headers.setdefault("Content-Type", "application/json")
        if cookies:
            request_headers["Cookie"] = "; ".join(
                f"{name}={value}" for name, value in cookies.items()
            )

        connection = http.client.HTTPConnection(
            "127.0.0.1",
            cls.server_port,
            timeout=15,
        )
        try:
            connection.request(
                method,
                path,
                body=body,
                headers=request_headers,
            )
            response = connection.getresponse()
            response_body = response.read()
            return HttpResponse(
                status=response.status,
                headers=tuple(response.getheaders()),
                body=response_body,
            )
        finally:
            connection.close()

    @staticmethod
    def _cookies_from(response: HttpResponse) -> dict[str, str]:
        cookies: dict[str, str] = {}
        for header in response.headers_for("Set-Cookie"):
            parsed = SimpleCookie()
            parsed.load(header)
            cookies.update(
                {name: morsel.value for name, morsel in parsed.items()}
            )
        return cookies

    @classmethod
    def _db_rows(
        cls,
        statement: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        async def read_rows() -> list[dict[str, Any]]:
            engine = create_async_engine(cls.database_url, poolclass=NullPool)
            try:
                async with engine.connect() as connection:
                    result = await connection.execute(
                        text(statement),
                        parameters or {},
                    )
                    return [dict(row) for row in result.mappings().all()]
            finally:
                await engine.dispose()

        return cls._run_async(read_rows())

    @classmethod
    def _db_scalar(
        cls,
        statement: str,
        parameters: dict[str, Any] | None = None,
    ) -> Any:
        async def read_scalar() -> Any:
            engine = create_async_engine(cls.database_url, poolclass=NullPool)
            try:
                async with engine.connect() as connection:
                    return await connection.scalar(
                        text(statement),
                        parameters or {},
                    )
            finally:
                await engine.dispose()

        return cls._run_async(read_scalar())

    @classmethod
    def _db_execute(
        cls,
        statement: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        async def execute() -> None:
            engine = create_async_engine(cls.database_url, poolclass=NullPool)
            try:
                async with engine.begin() as connection:
                    await connection.execute(text(statement), parameters or {})
            finally:
                await engine.dispose()

        cls._run_async(execute())

    def test_10_migration_preserves_accounts_and_removes_workspace_slug(self) -> None:
        self.assertEqual(
            self._db_scalar("SELECT version_num FROM alembic_version"),
            self.head_revision,
        )
        self.assertEqual(
            self._db_scalar(
                """
                SELECT count(*)
                FROM information_schema.columns
                WHERE table_name = 'tenants' AND column_name = 'workspace_slug'
                """
            ),
            0,
        )
        self.assertEqual(
            self._db_scalar(
                "SELECT count(*) FROM tenants WHERE contact_name IS NULL OR contact_email IS NULL"
            ),
            0,
        )
        self.assertEqual(
            self._db_scalar(
                "SELECT email::text FROM platform_admins WHERE admin_id = :id",
                {"id": PLATFORM_ADMIN_ID},
            ),
            PLATFORM_EMAIL,
        )
        self.assertEqual(
            self._db_scalar(
                """
                SELECT email::text
                FROM user_accounts
                WHERE tenant_id = :tenant_id AND id = :user_id
                """,
                {
                    "tenant_id": TENANT_ONE_ID,
                    "user_id": TENANT_ONE_USER_ID,
                },
            ),
            SHARED_MEMBER_EMAIL,
        )
        self.assertEqual(
            self._db_scalar(
                "SELECT credential_version FROM user_accounts WHERE id = :user_id",
                {"user_id": TENANT_ONE_USER_ID},
            ),
            1,
        )
        self.assertEqual(
            [
                (row["code"], row["display_name"])
                for row in self._db_rows(
                    """
                    SELECT code, display_name
                    FROM subscription_plans
                    ORDER BY plan_id
                    """
                )
            ],
            [
                ("FREE", "Free"),
                ("BASIC", "Basic"),
                ("PRO", "Professional"),
                ("ENTERPRISE", "Enterprise"),
            ],
        )
        self.assertEqual(
            self._db_scalar(
                """
                SELECT count(*)
                FROM tenant_subscriptions AS subscription
                JOIN subscription_plans AS plan
                  ON plan.plan_id = subscription.plan_id
                WHERE subscription.is_current IS TRUE
                  AND subscription.status = 'ACTIVE'
                  AND plan.code = 'BASIC'
                  AND subscription.ends_at IS NULL
                """
            ),
            3,
        )
        self.assertEqual(
            self._db_scalar(
                """
                SELECT count(*)
                FROM tenant_database_allocations
                WHERE mode = 'SHARED'
                  AND provisioning_state = 'READY'
                  AND ready_at IS NOT NULL
                """
            ),
            3,
        )
        self.assertEqual(
            self._db_scalar(
                """
                SELECT count(*)
                FROM platform_activity_events
                WHERE event_type = 'TENANT_CREATED'
                  AND actor_type = 'PLATFORM_ADMIN'
                  AND idempotency_key = 'tenant-created:' || tenant_id::text
                """
            ),
            3,
        )
        self.assertEqual(
            self._db_scalar(
                "SELECT count(*) FROM tenants WHERE status = 'ACTIVE'"
            ),
            3,
        )

    def test_12_migration_preflights_and_downgrade_are_deterministic(self) -> None:
        self._run_alembic_downgrade("0018")
        try:
            first_slug = self._db_scalar(
                "SELECT workspace_slug FROM tenants WHERE tenant_id = :tenant_id",
                {"tenant_id": TENANT_ONE_ID},
            )
            self.assertEqual(first_slug, "tenant-11111111-11111111")

            cases = (
                (
                    "UPDATE user_accounts SET email = :value WHERE id = :id",
                    {"value": SHARED_MEMBER_EMAIL, "id": TENANT_TWO_USER_ID},
                    "Duplicate emails",
                    "UPDATE user_accounts SET email = :value WHERE id = :id",
                    {"value": SECOND_MEMBER_EMAIL, "id": TENANT_TWO_USER_ID},
                ),
                (
                    "UPDATE tenants SET contact_name = NULL WHERE tenant_id = :id",
                    {"id": SHORT_ORG_TENANT_ID},
                    "Fix tenants",
                    "UPDATE tenants SET contact_name = 'Short Organization Contact' WHERE tenant_id = :id",
                    {"id": SHORT_ORG_TENANT_ID},
                ),
                (
                    "UPDATE tenants SET contact_email = :value WHERE tenant_id = :id",
                    {"value": SHARED_MEMBER_EMAIL, "id": TENANT_TWO_ID},
                    "Duplicate emails",
                    "UPDATE tenants SET contact_email = :value WHERE tenant_id = :id",
                    {"value": SECOND_MEMBER_EMAIL, "id": TENANT_TWO_ID},
                ),
                (
                    "UPDATE tenants SET contact_email = :value WHERE tenant_id = :id",
                    {"value": SHARED_MEMBER_EMAIL, "id": SHORT_ORG_TENANT_ID},
                    "belongs to another tenant account",
                    "UPDATE tenants SET contact_email = 'short-contact@example.com' WHERE tenant_id = :id",
                    {"id": SHORT_ORG_TENANT_ID},
                ),
            )
            for setup_sql, setup_params, diagnostic, restore_sql, restore_params in cases:
                with self.subTest(diagnostic=diagnostic):
                    self._db_execute(setup_sql, setup_params)
                    completed = self._invoke_alembic("upgrade", "0019")
                    self.assertNotEqual(completed.returncode, 0, completed.stdout)
                    self.assertIn(diagnostic, completed.stdout)
                    self._db_execute(restore_sql, restore_params)
        finally:
            self._db_execute(
                "UPDATE user_accounts SET email = :second_email WHERE id = :second_id",
                {
                    "second_email": SECOND_MEMBER_EMAIL,
                    "second_id": TENANT_TWO_USER_ID,
                },
            )
            self._db_execute(
                """
                UPDATE tenants SET
                    contact_name = 'Short Organization Contact',
                    contact_email = 'short-contact@example.com'
                WHERE tenant_id = :short_id
                """,
                {"short_id": SHORT_ORG_TENANT_ID},
            )
            self._db_execute(
                "UPDATE tenants SET contact_email = :second_email WHERE tenant_id = :tenant_two",
                {"second_email": SECOND_MEMBER_EMAIL, "tenant_two": TENANT_TWO_ID},
            )
            self._run_alembic("head")

    def test_15_only_one_current_subscription_is_allowed_per_tenant(self) -> None:
        with self.assertRaises(IntegrityError):
            self._db_execute(
                """
                INSERT INTO tenant_subscriptions
                    (subscription_id, tenant_id, plan_id, starts_at,
                     is_current, status)
                SELECT
                    :subscription_id,
                    :tenant_id,
                    plan_id,
                    CURRENT_TIMESTAMP,
                    true,
                    'ACTIVE'
                FROM subscription_plans
                WHERE code = 'FREE'
                """,
                {
                    "subscription_id": uuid.uuid4(),
                    "tenant_id": TENANT_ONE_ID,
                },
            )

    def test_16_database_allocation_requires_explicit_state(self) -> None:
        tenant_id = uuid.uuid4()
        self._db_execute(
            """
            INSERT INTO tenants
                (tenant_id, org_name, tenant_code, contact_name, contact_email,
                 created_by_admin_id)
            VALUES
                (:tenant_id, 'Allocation Invariant', :tenant_code,
                 'Allocation Contact', :contact_email, :admin_id)
            """,
            {
                "tenant_id": tenant_id,
                "tenant_code": f"ALLOC_{tenant_id.hex[:12].upper()}",
                "contact_email": f"allocation-{tenant_id.hex}@example.com",
                "admin_id": PLATFORM_ADMIN_ID,
            },
        )
        try:
            with self.assertRaises(IntegrityError):
                self._db_execute(
                    """
                    INSERT INTO tenant_database_allocations (tenant_id)
                    VALUES (:tenant_id)
                    """,
                    {"tenant_id": tenant_id},
                )
        finally:
            self._db_execute(
                "DELETE FROM tenants WHERE tenant_id = :tenant_id",
                {"tenant_id": tenant_id},
            )

    def test_20_citext_uniqueness_is_global_for_tenant_users(self) -> None:
        with self.assertRaises(IntegrityError):
            self._db_execute(
                """
                INSERT INTO platform_admins
                    (admin_id, name, email, password_hash)
                VALUES (:id, 'Duplicate', 'OPERATOR@EXAMPLE.COM', 'not-used')
                """,
                {"id": uuid.uuid4()},
            )

        with self.assertRaises(IntegrityError):
            self._db_execute(
                """
                INSERT INTO user_accounts
                    (tenant_id, id, display_name, email, password_hash, is_active)
                VALUES
                    (:tenant_id, :user_id, 'Duplicate',
                     'MEMBER@EXAMPLE.COM', 'not-used', true)
                """,
                {
                    "tenant_id": TENANT_ONE_ID,
                    "user_id": uuid.uuid4(),
                },
            )

        with self.assertRaises(IntegrityError):
            self._db_execute(
                """
                UPDATE tenants SET contact_email = :email
                WHERE tenant_id = :tenant_id
                """,
                {"email": SHARED_MEMBER_EMAIL, "tenant_id": TENANT_TWO_ID},
            )

    def test_30_successful_login_persists_argon2id_rehash(self) -> None:
        before = self._db_scalar(
            "SELECT password_hash FROM platform_admins WHERE admin_id = :id",
            {"id": LEGACY_ADMIN_ID},
        )
        self.assertTrue(before.startswith("$2"))

        response = self._request(
            "POST",
            "/auth/admin/login",
            payload={"email": LEGACY_EMAIL, "password": LEGACY_PASSWORD},
        )
        self.assertEqual(response.status, 200, response.body)
        self.assertIn("access_token", response.json())

        after = self._db_scalar(
            "SELECT password_hash FROM platform_admins WHERE admin_id = :id",
            {"id": LEGACY_ADMIN_ID},
        )
        self.assertTrue(after.startswith("$argon2id$"))
        self.assertNotEqual(after, before)

    def test_40_browser_session_restore_csrf_and_logout(self) -> None:
        login = self._request(
            "POST",
            "/auth/session/platform",
            payload={
                "email": f"  {PLATFORM_EMAIL.upper()}  ",
                "password": PLATFORM_PASSWORD,
            },
        )
        self.assertEqual(login.status, 200, login.body)
        principal = login.json()
        self.assertEqual(principal["principal_type"], "platform_admin")
        self.assertEqual(principal["role"], "Platform Admin")
        self.assertNotIn("token", principal)
        self.assertNotIn("access_token", principal)

        cookie_headers = login.headers_for("Set-Cookie")
        session_header = next(
            value for value in cookie_headers if value.startswith("mt_session=")
        )
        csrf_header = next(
            value for value in cookie_headers if value.startswith("mt_csrf=")
        )
        self.assertIn("HttpOnly", session_header)
        self.assertNotIn("HttpOnly", csrf_header)
        self.assertIn("SameSite=lax", session_header)
        self.assertIn("Path=/", session_header)
        self.assertIn("Max-Age=3600", session_header)

        cookies = self._cookies_from(login)
        self.assertIn("mt_session", cookies)
        self.assertIn("mt_csrf", cookies)
        session_token = cookies["mt_session"]
        csrf_token = cookies["mt_csrf"]
        session_row = self._db_rows(
            """
            SELECT token_hash, csrf_token_hash, revoked_at
            FROM user_sessions
            WHERE principal_id = :principal_id
            ORDER BY created_at DESC
            LIMIT 1
            """,
            {"principal_id": PLATFORM_ADMIN_ID},
        )[0]
        self.assertEqual(
            session_row["token_hash"],
            hashlib.sha256(session_token.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            session_row["csrf_token_hash"],
            hashlib.sha256(csrf_token.encode("utf-8")).hexdigest(),
        )
        self.assertNotEqual(session_row["token_hash"], session_token)
        self.assertIsNone(session_row["revoked_at"])

        restored = self._request("GET", "/auth/session", cookies=cookies)
        self.assertEqual(restored.status, 200, restored.body)
        self.assertEqual(restored.json()["principal_id"], str(PLATFORM_ADMIN_ID))

        missing_csrf = self._request(
            "DELETE",
            "/auth/session",
            cookies=cookies,
        )
        self.assertEqual(missing_csrf.status, 403)
        self.assertEqual(
            missing_csrf.json(),
            {"detail": "CSRF token missing or invalid"},
        )

        mismatched_csrf = self._request(
            "DELETE",
            "/auth/session",
            cookies=cookies,
            headers={"X-CSRF-Token": "wrong-token"},
        )
        self.assertEqual(mismatched_csrf.status, 403)

        logout = self._request(
            "DELETE",
            "/auth/session",
            cookies=cookies,
            headers={"X-CSRF-Token": csrf_token},
        )
        self.assertEqual(logout.status, 204, logout.body)
        self.assertTrue(
            all("Max-Age=0" in value for value in logout.headers_for("Set-Cookie"))
        )
        self.assertIsNotNone(
            self._db_scalar(
                """
                SELECT revoked_at
                FROM user_sessions
                WHERE token_hash = :token_hash
                """,
                {
                    "token_hash": hashlib.sha256(
                        session_token.encode("utf-8")
                    ).hexdigest()
                },
            )
        )

        after_logout = self._request(
            "GET",
            "/auth/session",
            cookies=cookies,
        )
        self.assertEqual(after_logout.status, 401)

    def test_45_expired_session_is_cleaned(self) -> None:
        login = self._request(
            "POST",
            "/auth/session/platform",
            payload={"email": PLATFORM_EMAIL, "password": PLATFORM_PASSWORD},
        )
        self.assertEqual(login.status, 200, login.body)
        cookies = self._cookies_from(login)
        token_hash = hashlib.sha256(
            cookies["mt_session"].encode("utf-8")
        ).hexdigest()

        self._db_execute(
            """
            UPDATE user_sessions
            SET expires_at = CURRENT_TIMESTAMP - INTERVAL '1 minute'
            WHERE token_hash = :token_hash
            """,
            {"token_hash": token_hash},
        )
        expired = self._request("GET", "/auth/session", cookies=cookies)
        self.assertEqual(expired.status, 401, expired.body)
        self.assertTrue(
            all(
                "Max-Age=0" in value
                for value in expired.headers_for("Set-Cookie")
            )
        )

        completed = subprocess.run(
            [sys.executable, "-m", "scripts.cleanup_auth_state"],
            cwd=REPOSITORY_ROOT,
            env=self._test_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertEqual(
            self._db_scalar(
                "SELECT count(*) FROM user_sessions "
                "WHERE token_hash = :token_hash",
                {"token_hash": token_hash},
            ),
            0,
        )
    def test_50_email_only_login_resolves_the_account_tenant(self) -> None:
        expected = (
            (SHARED_MEMBER_EMAIL, TENANT_ONE_USER_ID, TENANT_ONE_ID, "TENANT_11111111", "Tenant Admin"),
            (SECOND_MEMBER_EMAIL, TENANT_TWO_USER_ID, TENANT_TWO_ID, "TENANT_22222222", "Employee"),
        )
        for email, user_id, tenant_id, tenant_code, role in expected:
            with self.subTest(email=email):
                response = self._request(
                    "POST",
                    "/auth/session/tenant",
                    payload={
                        "email": f" {email.upper()} ",
                        "password": SHARED_MEMBER_PASSWORD,
                    },
                )
                self.assertEqual(response.status, 200, response.body)
                principal = response.json()
                self.assertEqual(principal["principal_id"], str(user_id))
                self.assertEqual(principal["tenant"]["tenant_id"], str(tenant_id))
                self.assertEqual(principal["tenant"]["tenant_code"], tenant_code)
                self.assertEqual(principal["role"], role)

    def test_55_authentication_failures_are_generic(self) -> None:
        cases = (
            {
                "email": "missing-member@example.com",
                "password": SHARED_MEMBER_PASSWORD,
            },
            {
                "email": SHARED_MEMBER_EMAIL,
                "password": "wrong-password",
            },
        )
        for payload in cases:
            with self.subTest(payload=payload):
                response = self._request(
                    "POST",
                    "/auth/session/tenant",
                    payload=payload,
                )
                self.assertEqual(response.status, 401, response.body)
                self.assertEqual(
                    response.json(),
                    {"code": "APP_ERROR", "detail": "Invalid credentials"},
                )

        self._db_execute(
            """
            UPDATE user_accounts SET is_active = false
            WHERE tenant_id = :tenant_id AND id = :user_id
            """,
            {
                "tenant_id": TENANT_ONE_ID,
                "user_id": TENANT_ONE_USER_ID,
            },
        )
        try:
            inactive = self._request(
                "POST",
                "/auth/session/tenant",
                payload={
                    "email": SHARED_MEMBER_EMAIL,
                    "password": SHARED_MEMBER_PASSWORD,
                },
            )
            self.assertEqual(inactive.status, 401, inactive.body)
            self.assertEqual(
                inactive.json(),
                {"code": "APP_ERROR", "detail": "Invalid credentials"},
            )
        finally:
            self._db_execute(
                """
                UPDATE user_accounts SET is_active = true
                WHERE tenant_id = :tenant_id AND id = :user_id
                """,
                {
                    "tenant_id": TENANT_ONE_ID,
                    "user_id": TENANT_ONE_USER_ID,
                },
            )

    def test_57_suspended_tenant_has_a_restricted_reactivatable_session(self) -> None:
        self._db_execute(
            "UPDATE tenants SET status = 'SUSPENDED' WHERE tenant_id = :tenant_id",
            {"tenant_id": TENANT_ONE_ID},
        )
        try:
            login = self._request(
                "POST",
                "/auth/session/tenant",
                payload={
                    "email": SHARED_MEMBER_EMAIL,
                    "password": SHARED_MEMBER_PASSWORD,
                },
            )
            self.assertEqual(login.status, 200, login.body)
            self.assertEqual(login.json()["tenant"]["status"], "SUSPENDED")
            cookies = self._cookies_from(login)

            restored = self._request("GET", "/auth/session", cookies=cookies)
            self.assertEqual(restored.status, 200, restored.body)
            self.assertEqual(restored.json()["tenant"]["status"], "SUSPENDED")

            blocked = self._request("GET", "/users", cookies=cookies)
            self.assertEqual(blocked.status, 403, blocked.body)
            self.assertEqual(blocked.json()["code"], "TENANT_SUSPENDED")

            self._db_execute(
                "UPDATE tenants SET status = 'ACTIVE' WHERE tenant_id = :tenant_id",
                {"tenant_id": TENANT_ONE_ID},
            )

            reactivated = self._request("GET", "/auth/session", cookies=cookies)
            self.assertEqual(reactivated.status, 200, reactivated.body)
            self.assertEqual(reactivated.json()["tenant"]["status"], "ACTIVE")
            self.assertEqual(
                self._request("GET", "/users", cookies=cookies).status,
                200,
            )

            csrf_token = cookies["mt_csrf"]
            logout = self._request(
                "DELETE",
                "/auth/session",
                cookies=cookies,
                headers={"X-CSRF-Token": csrf_token},
            )
            self.assertEqual(logout.status, 204, logout.body)
        finally:
            self._db_execute(
                "UPDATE tenants SET status = 'ACTIVE' WHERE tenant_id = :tenant_id",
                {"tenant_id": TENANT_ONE_ID},
            )

    def test_60_existing_platform_and_tenant_bearer_flows_work(self) -> None:
        admin_login = self._request(
            "POST",
            "/auth/admin/login",
            payload={"email": PLATFORM_EMAIL, "password": PLATFORM_PASSWORD},
        )
        self.assertEqual(admin_login.status, 200, admin_login.body)
        admin_token = admin_login.json()["access_token"]
        tenants = self._request(
            "GET",
            "/tenants",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(tenants.status, 200, tenants.body)
        self.assertEqual(len(tenants.json()["items"]), 3)

        tenant_login = self._request(
            "POST",
            "/auth/login",
            payload={
                "email": SHARED_MEMBER_EMAIL,
                "password": SHARED_MEMBER_PASSWORD,
            },
        )
        self.assertEqual(tenant_login.status, 200, tenant_login.body)
        tenant_token = tenant_login.json()["access_token"]
        users = self._request(
            "GET",
            "/users",
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        self.assertEqual(users.status, 200, users.body)
        self.assertEqual(len(users.json()), 1)

    def test_65_validation_errors_never_echo_passwords(self) -> None:
        admin_login = self._request(
            "POST",
            "/auth/admin/login",
            payload={"email": PLATFORM_EMAIL, "password": PLATFORM_PASSWORD},
        )
        self.assertEqual(admin_login.status, 200, admin_login.body)
        token = admin_login.json()["access_token"]
        plaintext_password = "Northstar!Secret42"
        response = self._request(
            "POST",
            "/tenants",
            headers={"Authorization": f"Bearer {token}"},
            payload={
                "org_name": "Northstar Labs",
                "tenant_code": "NORTHSTAR",
                "pan_number": "ABCDE1234F",
                "contact_name": "Admin User",
                "contact_designation": "Director",
                "contact_email": "admin@northstar.example",
                "tenant_admin_password": plaintext_password,
            },
        )
        self.assertEqual(response.status, 422, response.body)
        response_text = response.body.decode("utf-8")
        self.assertNotIn(plaintext_password, response_text)
        self.assertNotIn('"input"', response_text)

    def test_66_registration_rejects_an_existing_tenant_user_email(self) -> None:
        admin_login = self._request(
            "POST",
            "/auth/admin/login",
            payload={"email": PLATFORM_EMAIL, "password": PLATFORM_PASSWORD},
        )
        token = admin_login.json()["access_token"]
        response = self._request(
            "POST",
            "/tenants",
            headers={"Authorization": f"Bearer {token}"},
            payload={
                "org_name": "Conflicting Contact",
                "tenant_code": "CONFLICTING_CONTACT",
                "pan_number": "ABCDE1234F",
                "contact_name": "Existing Member",
                "contact_designation": "Director",
                "contact_email": SHARED_MEMBER_EMAIL,
            },
        )
        self.assertEqual(response.status, 409, response.body)
        self.assertEqual(
            response.json(),
            {
                "code": "APP_ERROR",
                "detail": "This primary contact email is already used by a tenant account",
            },
        )

    def test_70_tenant_creation_persists_complete_free_tenant_graph(self) -> None:
        admin_login = self._request(
            "POST",
            "/auth/admin/login",
            payload={"email": PLATFORM_EMAIL, "password": PLATFORM_PASSWORD},
        )
        self.assertEqual(admin_login.status, 200, admin_login.body)
        token = admin_login.json()["access_token"]

        created = self._request(
            "POST",
            "/tenants",
            headers={"Authorization": f"Bearer {token}"},
            payload={
                "org_name": "Orchid Systems",
                "tenant_code": "ORCHID_SYSTEMS",
                "pan_number": "ABCDE1234F",
                "contact_name": "Morgan Lee",
                "contact_designation": "Director",
                "contact_email": "owner@orchid.example",
            },
        )
        self.assertEqual(created.status, 201, created.body)
        body = created.json()
        tenant_id = uuid.UUID(body["tenant_id"])
        self.assertEqual(body["subscription_plan"], "Free")
        self.assertEqual(body["subscription_plan_code"], "FREE")
        self.assertIsNone(body["subscription_ends_at"])
        self.assertEqual(body["status"], "ACTIVE")
        self.assertEqual(body["database_mode"], "SHARED")
        self.assertEqual(body["database_provisioning_state"], "READY")

        graph = self._db_rows(
            """
            SELECT
                plan.code AS plan_code,
                subscription.ends_at,
                subscription.is_current,
                allocation.mode,
                allocation.provisioning_state,
                allocation.ready_at,
                activity.event_type,
                activity.actor_id,
                activity.metadata->>'tenant_code' AS event_tenant_code
            FROM tenants AS tenant
            JOIN tenant_subscriptions AS subscription
              ON subscription.tenant_id = tenant.tenant_id
             AND subscription.is_current IS TRUE
            JOIN subscription_plans AS plan
              ON plan.plan_id = subscription.plan_id
            JOIN tenant_database_allocations AS allocation
              ON allocation.tenant_id = tenant.tenant_id
            JOIN platform_activity_events AS activity
              ON activity.tenant_id = tenant.tenant_id
             AND activity.event_type = 'TENANT_CREATED'
            WHERE tenant.tenant_id = :tenant_id
            """,
            {"tenant_id": tenant_id},
        )
        self.assertEqual(len(graph), 1)
        row = graph[0]
        self.assertEqual(row["plan_code"], "FREE")
        self.assertIsNone(row["ends_at"])
        self.assertTrue(row["is_current"])
        self.assertEqual(row["mode"], "SHARED")
        self.assertEqual(row["provisioning_state"], "READY")
        self.assertIsNotNone(row["ready_at"])
        self.assertEqual(row["event_type"], "TENANT_CREATED")
        self.assertEqual(row["actor_id"], PLATFORM_ADMIN_ID)
        self.assertEqual(row["event_tenant_code"], "ORCHID_SYSTEMS")
        self.assertEqual(
            self._db_scalar(
                "SELECT count(*) FROM user_accounts WHERE tenant_id = :tenant_id",
                {"tenant_id": tenant_id},
            ),
            0,
        )
        self.assertEqual(
            self._db_scalar(
                "SELECT count(*) FROM roles WHERE tenant_id = :tenant_id",
                {"tenant_id": tenant_id},
            ),
            0,
        )

    def test_71_bootstrap_forces_password_change_and_rotates_credentials(self) -> None:
        tenant_id = self._db_scalar(
            "SELECT tenant_id FROM tenants WHERE tenant_code = 'ORCHID_SYSTEMS'"
        )
        self.assertIsNotNone(tenant_id)
        self._db_execute(
            """
            INSERT INTO roles
                (id, tenant_id, role_code, role_name, description, is_system, is_active)
            VALUES
                (:role_id, :tenant_id, 'TENANT_ADMIN', 'Tenant Admin',
                 'Provisioned by UAM integration fixture', true, true)
            """,
            {"role_id": uuid.uuid4(), "tenant_id": tenant_id},
        )

        def run_bootstrap(*extra: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.bootstrap_tenant_admin",
                    "--tenant-code",
                    "ORCHID_SYSTEMS",
                    *extra,
                ],
                cwd=REPOSITORY_ROOT,
                env=self._test_environment(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,
                check=False,
            )

        created = run_bootstrap()
        self.assertEqual(created.returncode, 0, created.stdout)
        first_password = re.search(r"Temporary password: (\S+)", created.stdout)
        self.assertIsNotNone(first_password, created.stdout)

        duplicate = run_bootstrap()
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("A Tenant Admin already exists", duplicate.stdout)
        self.assertNotIn("Temporary password:", duplicate.stdout)

        rotated = run_bootstrap("--rotate-pending")
        self.assertEqual(rotated.returncode, 0, rotated.stdout)
        rotated_match = re.search(r"Temporary password: (\S+)", rotated.stdout)
        self.assertIsNotNone(rotated_match, rotated.stdout)
        temporary_password = rotated_match.group(1)
        self.assertNotEqual(temporary_password, first_password.group(1))

        browser_login = self._request(
            "POST",
            "/auth/session/tenant",
            payload={
                "email": "OWNER@ORCHID.EXAMPLE",
                "password": temporary_password,
            },
        )
        self.assertEqual(browser_login.status, 200, browser_login.body)
        self.assertTrue(browser_login.json()["password_change_required"])
        old_cookies = self._cookies_from(browser_login)
        blocked = self._request("GET", "/users", cookies=old_cookies)
        self.assertEqual(blocked.status, 403, blocked.body)
        self.assertEqual(blocked.json()["code"], "PASSWORD_CHANGE_REQUIRED")

        bearer_login = self._request(
            "POST",
            "/auth/login",
            payload={
                "email": "owner@orchid.example",
                "password": temporary_password,
            },
        )
        self.assertEqual(bearer_login.status, 200, bearer_login.body)
        old_bearer = bearer_login.json()["access_token"]

        changed = self._request(
            "POST",
            "/auth/password/change",
            payload={
                "current_password": temporary_password,
                "new_password": "Permanent!Harbor96",
            },
            cookies=old_cookies,
            headers={"X-CSRF-Token": old_cookies["mt_csrf"]},
        )
        self.assertEqual(changed.status, 200, changed.body)
        self.assertFalse(changed.json()["principal"]["password_change_required"])
        self.assertIsNone(changed.json()["replacement_access_token"])
        new_cookies = self._cookies_from(changed)
        self.assertNotEqual(new_cookies["mt_session"], old_cookies["mt_session"])
        self.assertEqual(
            self._request("GET", "/auth/session", cookies=old_cookies).status,
            401,
        )
        self.assertEqual(
            self._request("GET", "/auth/session", cookies=new_cookies).status,
            200,
        )
        self.assertEqual(
            self._request(
                "GET",
                "/users",
                headers={"Authorization": f"Bearer {old_bearer}"},
            ).status,
            401,
        )

        bearer_after_setup = self._request(
            "POST",
            "/auth/login",
            payload={
                "email": "owner@orchid.example",
                "password": "Permanent!Harbor96",
            },
        ).json()["access_token"]
        bearer_change = self._request(
            "POST",
            "/auth/password/change",
            payload={
                "current_password": "Permanent!Harbor96",
                "new_password": "Permanent!Summit97",
            },
            headers={"Authorization": f"Bearer {bearer_after_setup}"},
        )
        self.assertEqual(bearer_change.status, 200, bearer_change.body)
        replacement_bearer = bearer_change.json()["replacement_access_token"]
        self.assertIsNotNone(replacement_bearer)
        self.assertEqual(bearer_change.json()["token_type"], "bearer")
        self.assertEqual(
            self._request(
                "GET",
                "/users",
                headers={"Authorization": f"Bearer {bearer_after_setup}"},
            ).status,
            401,
        )
        self.assertEqual(
            self._request(
                "GET",
                "/users",
                headers={"Authorization": f"Bearer {replacement_bearer}"},
            ).status,
            200,
        )

        established_rotation = run_bootstrap("--rotate-pending")
        self.assertNotEqual(established_rotation.returncode, 0)
        self.assertIn("completed password setup", established_rotation.stdout)
        self.assertNotIn("Temporary password:", established_rotation.stdout)

        audit_values = self._db_rows(
            """
            SELECT action, coalesce(new_value::text, '') AS value
            FROM audit_logs
            WHERE tenant_id = :tenant_id
              AND action IN ('BOOTSTRAP_TENANT_ADMIN', 'ROTATE_BOOTSTRAP_PASSWORD')
            ORDER BY changed_at
            """,
            {"tenant_id": tenant_id},
        )
        self.assertEqual(
            [row["action"] for row in audit_values],
            ["BOOTSTRAP_TENANT_ADMIN", "ROTATE_BOOTSTRAP_PASSWORD"],
        )
        self.assertTrue(
            all(temporary_password not in row["value"] for row in audit_values)
        )

    def test_70_platform_dashboard_uses_real_aggregates_and_role_guard(self) -> None:
        admin_login = self._request(
            "POST",
            "/auth/admin/login",
            payload={"email": PLATFORM_EMAIL, "password": PLATFORM_PASSWORD},
        )
        self.assertEqual(admin_login.status, 200, admin_login.body)
        admin_headers = {
            "Authorization": (
                f"Bearer {admin_login.json()['access_token']}"
            )
        }

        response = self._request(
            "GET",
            (
                "/platform/dashboard"
                "?growth_months=6&registration_days=7&activity_limit=2"
            ),
            headers=admin_headers,
        )
        if response.status == 500:
            self.server_log.flush()
            self.server_log.seek(0)
            server_output = self.server_log.read().decode("utf-8", errors="replace")
            self.server_log.seek(0, os.SEEK_END)
            self.fail(f"Dashboard returned 500:\n{server_output}")
        self.assertEqual(response.status, 200, response.body)
        self.assertEqual(response.header("Cache-Control"), "private, no-store")
        dashboard = response.json()
        self.assertEqual(
            set(dashboard),
            {
                "generated_at",
                "filters",
                "kpis",
                "charts",
                "recent_activity",
            },
        )
        self.assertEqual(
            dashboard["filters"],
            {"growth_months": 6, "registration_days": 7},
        )
        self.assertEqual(
            dashboard["kpis"],
            {
                "total_tenants": 3,
                "active_tenants": 3,
                "dedicated_databases": 0,
                "shared_database_tenants": 3,
                "total_users": 2,
                "new_tenants_this_month": 3,
                "expired_subscriptions": 0,
            },
        )
        self.assertEqual(len(dashboard["charts"]["tenant_growth"]), 6)
        self.assertEqual(
            dashboard["charts"]["tenant_growth"][-1]["total_tenants"],
            3,
        )
        self.assertEqual(len(dashboard["charts"]["new_registrations"]), 7)
        self.assertEqual(
            sum(
                point["new_tenants"]
                for point in dashboard["charts"]["new_registrations"]
            ),
            3,
        )
        self.assertEqual(
            dashboard["charts"]["subscription_distribution"],
            [
                {
                    "plan_code": "BASIC",
                    "plan_name": "Basic",
                    "tenant_count": 3,
                }
            ],
        )
        self.assertEqual(len(dashboard["recent_activity"]), 2)
        self.assertTrue(
            all(
                activity["event_type"] == "TENANT_CREATED"
                for activity in dashboard["recent_activity"]
            )
        )

        # Exercise every condition in the Active Tenant definition. A Ready
        # allocation alone is insufficient when the tenant is suspended or
        # its current subscription is not ACTIVE. Expiration is derived from
        # database time and counted independently.
        try:
            self._db_execute(
                """
                UPDATE tenant_database_allocations
                SET mode = 'DEDICATED'
                WHERE tenant_id = :tenant_id
                """,
                {"tenant_id": TENANT_ONE_ID},
            )
            self._db_execute(
                """
                UPDATE tenants
                SET status = 'SUSPENDED'
                WHERE tenant_id = :tenant_id
                """,
                {"tenant_id": TENANT_TWO_ID},
            )
            self._db_execute(
                """
                UPDATE tenant_subscriptions
                SET starts_at = CURRENT_TIMESTAMP - INTERVAL '2 days',
                    ends_at = CURRENT_TIMESTAMP - INTERVAL '1 day',
                    status = 'EXPIRED'
                WHERE tenant_id = :tenant_id AND is_current IS TRUE
                """,
                {"tenant_id": TENANT_TWO_ID},
            )
            self._db_execute(
                """
                UPDATE tenant_subscriptions
                SET status = 'CANCELLED'
                WHERE tenant_id = :tenant_id AND is_current IS TRUE
                """,
                {"tenant_id": SHORT_ORG_TENANT_ID},
            )

            changed = self._request(
                "GET",
                "/platform/dashboard",
                headers=admin_headers,
            )
            self.assertEqual(changed.status, 200, changed.body)
            changed_kpis = changed.json()["kpis"]
            self.assertEqual(changed_kpis["active_tenants"], 1)
            self.assertEqual(changed_kpis["dedicated_databases"], 1)
            self.assertEqual(changed_kpis["shared_database_tenants"], 2)
            self.assertEqual(changed_kpis["expired_subscriptions"], 1)
        finally:
            self._db_execute(
                """
                UPDATE tenant_database_allocations
                SET mode = 'SHARED'
                WHERE tenant_id = :tenant_id
                """,
                {"tenant_id": TENANT_ONE_ID},
            )
            self._db_execute(
                """
                UPDATE tenants
                SET status = 'ACTIVE'
                WHERE tenant_id = :tenant_id
                """,
                {"tenant_id": TENANT_TWO_ID},
            )
            self._db_execute(
                """
                UPDATE tenant_subscriptions
                SET ends_at = NULL, status = 'ACTIVE'
                WHERE tenant_id IN (:tenant_two, :tenant_three)
                  AND is_current IS TRUE
                """,
                {
                    "tenant_two": TENANT_TWO_ID,
                    "tenant_three": SHORT_ORG_TENANT_ID,
                },
            )

        invalid_range = self._request(
            "GET",
            "/platform/dashboard?growth_months=5",
            headers=admin_headers,
        )
        self.assertEqual(invalid_range.status, 422, invalid_range.body)

        tenant_login = self._request(
            "POST",
            "/auth/login",
            payload={
                "email": SHARED_MEMBER_EMAIL,
                "password": SHARED_MEMBER_PASSWORD,
            },
        )
        self.assertEqual(tenant_login.status, 200, tenant_login.body)
        forbidden = self._request(
            "GET",
            "/platform/dashboard",
            headers={
                "Authorization": (
                    f"Bearer {tenant_login.json()['access_token']}"
                )
            },
        )
        self.assertEqual(forbidden.status, 403, forbidden.body)
        self.assertEqual(
            forbidden.json(),
            {
                "code": "APP_ERROR",
                "detail": "Platform administrator access required",
            },
        )

    def test_72_deleted_tenant_activity_retains_snapshot_and_idempotency(self) -> None:
        tenant_id = self._db_scalar(
            """
            SELECT tenant_id
            FROM tenants
            WHERE tenant_code = 'ORCHID_SYSTEMS'
            """
        )
        self.assertIsNotNone(
            tenant_id,
            "the tenant-creation scenario must run before snapshot retention",
        )
        idempotency_key = f"tenant-created:{tenant_id}"

        with self.assertRaises(IntegrityError):
            self._db_execute(
                """
                INSERT INTO platform_activity_events
                    (activity_id, event_type, tenant_id,
                     tenant_name_snapshot, actor_id, actor_type,
                     metadata, idempotency_key)
                VALUES
                    (:activity_id, 'TENANT_CREATED', :tenant_id,
                     'Duplicate', :actor_id, 'PLATFORM_ADMIN',
                     '{}'::jsonb, :idempotency_key)
                """,
                {
                    "activity_id": uuid.uuid4(),
                    "tenant_id": tenant_id,
                    "actor_id": PLATFORM_ADMIN_ID,
                    "idempotency_key": idempotency_key,
                },
            )

        self._db_execute(
            "DELETE FROM tenants WHERE tenant_id = :tenant_id",
            {"tenant_id": tenant_id},
        )
        event = self._db_rows(
            """
            SELECT
                tenant_id,
                tenant_name_snapshot,
                metadata->>'tenant_code' AS tenant_code,
                idempotency_key
            FROM platform_activity_events
            WHERE idempotency_key = :idempotency_key
            """,
            {"idempotency_key": idempotency_key},
        )
        self.assertEqual(
            event,
            [
                {
                    "tenant_id": None,
                    "tenant_name_snapshot": "Orchid Systems",
                    "tenant_code": "ORCHID_SYSTEMS",
                    "idempotency_key": idempotency_key,
                }
            ],
        )

    def test_75_readiness_is_public_and_reports_only_bounded_status(self) -> None:
        response = self._request("GET", "/health/ready")
        self.assertEqual(response.status, 200, response.body)
        self.assertEqual(response.header("Cache-Control"), "no-store")
        readiness = response.json()
        self.assertEqual(
            set(readiness),
            {"status", "checked_at", "checks"},
        )
        self.assertEqual(readiness["status"], "healthy")
        self.assertEqual(
            readiness["checks"],
            {"api": "healthy", "database": "healthy"},
        )

    def test_77_task_management_rls_isolates_raw_database_access(self) -> None:
        project_id = uuid.UUID("77777777-7777-4777-8777-777777777777")

        async def exercise() -> tuple[int, int, int, int]:
            engine = create_async_engine(self.database_url, poolclass=NullPool)
            try:
                async with engine.connect() as connection:
                    bypasses_rls = bool(
                        await connection.scalar(
                            text(
                                "SELECT rolsuper OR rolbypassrls "
                                "FROM pg_roles WHERE rolname = current_user"
                            )
                        )
                    )
                if bypasses_rls:
                    raise unittest.SkipTest(
                        "RLS isolation requires a non-superuser, non-BYPASSRLS integration role"
                    )
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            "SELECT set_config('app.principal_type', 'admin', true), "
                            "set_config('app.tenant_id', '', true)"
                        )
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO projects
                                (tenant_id, project_id, project_key, name, status,
                                 priority, next_task_number, version)
                            VALUES
                                (:tenant_id, :project_id, 'RLS', 'RLS verification',
                                 'Not Started', 'Medium', 1, 1)
                            """
                        ),
                        {"tenant_id": TENANT_ONE_ID, "project_id": project_id},
                    )

                async with engine.begin() as connection:
                    no_context = int(
                        await connection.scalar(text("SELECT count(*) FROM projects"))
                    )

                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            "SELECT set_config('app.principal_type', 'user', true), "
                            "set_config('app.tenant_id', :tenant_id, true)"
                        ),
                        {"tenant_id": str(TENANT_ONE_ID)},
                    )
                    own_tenant = int(
                        await connection.scalar(
                            text("SELECT count(*) FROM projects WHERE project_id = :project_id"),
                            {"project_id": project_id},
                        )
                    )

                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            "SELECT set_config('app.principal_type', 'user', true), "
                            "set_config('app.tenant_id', :tenant_id, true)"
                        ),
                        {"tenant_id": str(TENANT_TWO_ID)},
                    )
                    other_tenant = int(
                        await connection.scalar(
                            text("SELECT count(*) FROM projects WHERE project_id = :project_id"),
                            {"project_id": project_id},
                        )
                    )
                    update_result = await connection.execute(
                        text("UPDATE projects SET name = 'leaked' WHERE project_id = :project_id"),
                        {"project_id": project_id},
                    )
                    cross_tenant_updates = int(update_result.rowcount or 0)
                return no_context, own_tenant, other_tenant, cross_tenant_updates
            finally:
                await engine.dispose()

        self.assertEqual(self._run_async(exercise()), (0, 1, 0, 0))

    def test_80_account_throttling_locks_on_fifth_failure(self) -> None:
        payload = {"email": THROTTLE_EMAIL, "password": "wrong-password"}
        for attempt in range(1, 6):
            response = self._request(
                "POST",
                "/auth/session/platform",
                payload=payload,
            )
            if attempt < 5:
                self.assertEqual(response.status, 401, response.body)
                self.assertEqual(
                    response.json(),
                    {"code": "APP_ERROR", "detail": "Invalid credentials"},
                )
            else:
                self.assertEqual(response.status, 429, response.body)
                self.assertEqual(
                    response.json(),
                    {"detail": "Unable to sign in. Please try again later."},
                )
                self.assertGreater(int(response.header("Retry-After") or "0"), 0)

        correct_password_is_still_generic = self._request(
            "POST",
            "/auth/session/platform",
            payload={
                "email": THROTTLE_EMAIL,
                "password": THROTTLE_PASSWORD,
            },
        )
        self.assertEqual(correct_password_is_still_generic.status, 429)
        self.assertEqual(
            correct_password_is_still_generic.json(),
            {"detail": "Unable to sign in. Please try again later."},
        )

if __name__ == "__main__":
    unittest.main()
