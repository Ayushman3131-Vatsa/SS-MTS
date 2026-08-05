import json
import unittest
import uuid
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI, Response as FastAPIResponse
from pydantic import ValidationError

from app.common.deps import Principal, require_platform_admin
from app.core.exceptions import ForbiddenError
from app.main import app as production_app
from app.modules.platform_dashboard import router as dashboard_router
from app.modules.platform_dashboard import service
from app.schemas.platform_dashboard import (
    ActivityTenant,
    DashboardCharts,
    DashboardFilters,
    DashboardKpis,
    NewRegistrationPoint,
    PlatformDashboardResponse,
    ReadinessChecks,
    ReadinessResponse,
    RecentActivity,
    SubscriptionDistributionPoint,
    TenantGrowthPoint,
)


ADMIN_ID = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
TENANT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
ACTIVITY_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def _dashboard_response() -> PlatformDashboardResponse:
    return PlatformDashboardResponse(
        generated_at=NOW,
        filters=DashboardFilters(growth_months=12, registration_days=30),
        kpis=DashboardKpis(
            total_tenants=3,
            active_tenants=2,
            dedicated_databases=1,
            shared_database_tenants=2,
            total_users=14,
            new_tenants_this_month=1,
            expired_subscriptions=1,
        ),
        charts=DashboardCharts(
            tenant_growth=[
                TenantGrowthPoint(
                    month=date(2026, 7, 1),
                    total_tenants=3,
                )
            ],
            new_registrations=[
                NewRegistrationPoint(
                    date=date(2026, 7, 23),
                    new_tenants=1,
                )
            ],
            subscription_distribution=[
                SubscriptionDistributionPoint(
                    plan_code="BASIC",
                    plan_name="Basic",
                    tenant_count=3,
                )
            ],
        ),
        recent_activity=[
            RecentActivity(
                activity_id=ACTIVITY_ID,
                event_type="TENANT_CREATED",
                occurred_at=NOW,
                tenant=ActivityTenant(
                    tenant_id=TENANT_ID,
                    tenant_name="Northstar",
                ),
                metadata={},
            )
        ],
    )


async def _asgi_get(app: FastAPI, path: str, query_string: str = ""):
    sent: list[dict] = []
    received = False

    async def receive() -> dict:
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        sent.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query_string.encode(),
            "headers": [],
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 12345),
            "root_path": "",
        },
        receive,
        send,
    )
    start = next(message for message in sent if message["type"] == "http.response.start")
    body = b"".join(
        message.get("body", b"")
        for message in sent
        if message["type"] == "http.response.body"
    )
    headers = {
        key.decode().lower(): value.decode()
        for key, value in start.get("headers", [])
    }
    return start["status"], headers, body


class DashboardSchemaTests(unittest.TestCase):
    def test_response_contract_rejects_unknown_fields(self) -> None:
        payload = _dashboard_response().model_dump()
        payload["unexpected"] = True
        with self.assertRaises(ValidationError):
            PlatformDashboardResponse.model_validate(payload)

    def test_response_contract_rejects_unknown_plan_and_event_codes(self) -> None:
        with self.assertRaises(ValidationError):
            SubscriptionDistributionPoint(
                plan_code="CUSTOM",
                plan_name="Custom",
                tenant_count=1,
            )
        with self.assertRaises(ValidationError):
            RecentActivity(
                activity_id=ACTIVITY_ID,
                event_type="UNKNOWN",
                occurred_at=NOW,
                tenant=ActivityTenant(
                    tenant_id=TENANT_ID,
                    tenant_name="Northstar",
                ),
                metadata={},
            )

    def test_response_contract_accepts_current_offering_event_codes(self) -> None:
        activity = RecentActivity(
            activity_id=ACTIVITY_ID,
            event_type="OFFERING_GRANTED",
            occurred_at=NOW,
            tenant=ActivityTenant(
                tenant_id=TENANT_ID,
                tenant_name="Northstar",
            ),
            metadata={"offering": {"display_name": "Payroll"}},
        )
        self.assertEqual(activity.event_type.value, "OFFERING_GRANTED")


class DashboardAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_tenant_principal_is_forbidden(self) -> None:
        principal = Principal(
            type="user",
            id=uuid.uuid4(),
            email="member@example.com",
            tenant_id=TENANT_ID,
            role="Tenant Admin",
        )
        with self.assertRaises(ForbiddenError):
            await require_platform_admin(principal)


class DashboardOpenAPITests(unittest.TestCase):
    def test_dashboard_is_protected_and_readiness_is_public(self) -> None:
        schema = production_app.openapi()
        self.assertEqual(
            schema["paths"]["/platform/dashboard"]["get"]["security"],
            [{"BearerAuth": []}, {"BrowserSession": []}],
        )
        self.assertEqual(
            schema["paths"]["/health/ready"]["get"]["security"],
            [],
        )


class _Transaction(AbstractAsyncContextManager):
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False


class _DashboardSession:
    def __init__(self):
        self.execute = AsyncMock()

    def begin(self) -> _Transaction:
        return _Transaction()


class DashboardServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_service_maps_one_consistent_snapshot_to_contract(self) -> None:
        db = _DashboardSession()
        kpis = {
            "generated_at": NOW,
            "total_tenants": 3,
            "active_tenants": 2,
            "dedicated_databases": 1,
            "shared_database_tenants": 2,
            "total_users": 14,
            "new_tenants_this_month": 1,
            "expired_subscriptions": 1,
        }
        with (
            patch.object(
                service.repository,
                "get_kpis",
                new=AsyncMock(return_value=kpis),
            ),
            patch.object(
                service.repository,
                "get_tenant_growth",
                new=AsyncMock(
                    return_value=[
                        {
                            "month": date(2026, 7, 1),
                            "total_tenants": 3,
                        }
                    ]
                ),
            ),
            patch.object(
                service.repository,
                "get_new_registrations",
                new=AsyncMock(
                    return_value=[
                        {
                            "date": date(2026, 7, 23),
                            "new_tenants": 1,
                        }
                    ]
                ),
            ),
            patch.object(
                service.repository,
                "get_subscription_distribution",
                new=AsyncMock(
                    return_value=[
                        {
                            "plan_code": "BASIC",
                            "plan_name": "Basic",
                            "tenant_count": 3,
                        }
                    ]
                ),
            ),
            patch.object(
                service.repository,
                "get_recent_activity",
                new=AsyncMock(
                    return_value=[
                        {
                            "activity_id": ACTIVITY_ID,
                            "event_type": "TENANT_CREATED",
                            "occurred_at": NOW,
                            "tenant_id": TENANT_ID,
                            "tenant_name": "Northstar",
                            "metadata": None,
                        }
                    ]
                ),
            ),
        ):
            result = await service.get_platform_dashboard(
                db,  # type: ignore[arg-type]
                growth_months=12,
                registration_days=30,
                activity_limit=10,
            )

        self.assertEqual(result.kpis.total_tenants, 3)
        self.assertEqual(result.charts.tenant_growth[0].total_tenants, 3)
        self.assertEqual(result.recent_activity[0].metadata, {})
        db.execute.assert_awaited_once()
        self.assertIn(
            "REPEATABLE READ, READ ONLY",
            str(db.execute.await_args.args[0]),
        )


class DashboardRouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(dashboard_router.router)

        async def admin_override() -> Principal:
            return Principal(
                type="admin",
                id=ADMIN_ID,
                email="operator@example.com",
            )

        async def dashboard_db_override():
            yield object()

        self.app.dependency_overrides[require_platform_admin] = admin_override
        self.app.dependency_overrides[
            dashboard_router.get_dashboard_db
        ] = dashboard_db_override

    async def test_dashboard_response_and_no_store_header(self) -> None:
        get_dashboard = AsyncMock(return_value=_dashboard_response())
        with patch.object(
            dashboard_router.service,
            "get_platform_dashboard",
            new=get_dashboard,
        ):
            status_code, headers, body = await _asgi_get(
                self.app,
                "/platform/dashboard",
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(headers["cache-control"], "private, no-store")
        self.assertEqual(
            set(json.loads(body)),
            {
                "generated_at",
                "filters",
                "kpis",
                "charts",
                "recent_activity",
            },
        )
        get_dashboard.assert_awaited_once()
        self.assertEqual(get_dashboard.await_args.kwargs["growth_months"], 12)
        self.assertEqual(
            get_dashboard.await_args.kwargs["registration_days"],
            30,
        )
        self.assertEqual(get_dashboard.await_args.kwargs["activity_limit"], 10)

    async def test_invalid_ranges_are_rejected_before_service(self) -> None:
        get_dashboard = AsyncMock(return_value=_dashboard_response())
        with patch.object(
            dashboard_router.service,
            "get_platform_dashboard",
            new=get_dashboard,
        ):
            cases = (
                "growth_months=5",
                "registration_days=14",
                "activity_limit=0",
                "activity_limit=26",
            )
            for query_string in cases:
                with self.subTest(query_string=query_string):
                    status_code, _, _ = await _asgi_get(
                        self.app,
                        "/platform/dashboard",
                        query_string,
                    )
                    self.assertEqual(status_code, 422)

        get_dashboard.assert_not_awaited()

    async def test_allowed_integer_presets_are_parsed_from_query_strings(
        self,
    ) -> None:
        get_dashboard = AsyncMock(return_value=_dashboard_response())
        with patch.object(
            dashboard_router.service,
            "get_platform_dashboard",
            new=get_dashboard,
        ):
            status_code, _, _ = await _asgi_get(
                self.app,
                "/platform/dashboard",
                "growth_months=6&registration_days=7&activity_limit=25",
            )

        self.assertEqual(status_code, 200)
        self.assertEqual(get_dashboard.await_args.kwargs["growth_months"], 6)
        self.assertEqual(
            get_dashboard.await_args.kwargs["registration_days"],
            7,
        )
        self.assertEqual(get_dashboard.await_args.kwargs["activity_limit"], 25)


class ReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def test_database_success_is_healthy(self) -> None:
        db = type("Database", (), {"execute": AsyncMock()})()
        result = await service.get_readiness(db)
        self.assertEqual(
            result,
            ReadinessResponse(
                status="healthy",
                checked_at=result.checked_at,
                checks=ReadinessChecks(
                    api="healthy",
                    database="healthy",
                ),
            ),
        )

    async def test_database_failure_is_degraded_without_error_details(self) -> None:
        db = type(
            "Database",
            (),
            {"execute": AsyncMock(side_effect=RuntimeError("secret host"))},
        )()
        with self.assertLogs(service.logger, level="WARNING") as captured_logs:
            result = await service.get_readiness(db)
        serialized = result.model_dump_json()
        self.assertEqual(result.status, "degraded")
        self.assertEqual(result.checks.database, "unavailable")
        self.assertNotIn("secret host", serialized)
        self.assertIn(
            "Primary database readiness check failed (RuntimeError)",
            captured_logs.output[0],
        )

    async def test_readiness_route_returns_503_and_no_store_when_degraded(
        self,
    ) -> None:
        response = FastAPIResponse()
        degraded = ReadinessResponse(
            status="degraded",
            checked_at=NOW,
            checks=ReadinessChecks(
                api="healthy",
                database="unavailable",
            ),
        )
        with patch.object(
            dashboard_router.service,
            "get_readiness",
            new=AsyncMock(return_value=degraded),
        ):
            result = await dashboard_router.readiness(
                response,
                object(),  # type: ignore[arg-type]
            )

        self.assertEqual(result, degraded)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
