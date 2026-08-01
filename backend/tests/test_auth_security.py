import json
import unittest
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import Response

from app.common.config import Settings
from app.auth.middleware import (
    AuthenticationMiddleware,
    PUBLIC_ROUTES,
    db_manager,
)
from app.common.middleware.security_middleware import (
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.auth.login import router as auth_router
from app.auth.login.service import (
    BrowserAuthenticationResult,
    _create_browser_session,
    browser_session_csrf_is_valid,
    digest_secret,
    platform_account_throttle_key,
)
from app.auth.schemas.auth import (
    PlatformSessionLoginRequest,
    SessionPrincipalResponse,
    TenantSessionLoginRequest,
)


class AuthSchemaTests(unittest.TestCase):
    def test_tenant_login_normalizes_only_workspace_and_email(self) -> None:
        payload = TenantSessionLoginRequest(
            workspace_slug=" Northstar-Labs ",
            email=" Person@Example.COM ",
            password="  exact password  ",
        )
        self.assertEqual(payload.workspace_slug, "northstar-labs")
        self.assertEqual(str(payload.email), "person@example.com")
        self.assertEqual(payload.password, "  exact password  ")

    def test_login_does_not_apply_creation_strength_policy(self) -> None:
        payload = PlatformSessionLoginRequest(
            email="admin@example.com",
            password="legacy",
        )
        self.assertEqual(payload.password, "legacy")

    def test_login_rejects_unexpected_fields(self) -> None:
        with self.assertRaises(ValidationError):
            PlatformSessionLoginRequest.model_validate(
                {
                    "email": "admin@example.com",
                    "password": "legacy",
                    "role": "Platform Admin",
                }
            )

    def test_workspace_slug_rules_are_enforced(self) -> None:
        for invalid_slug in (
            "ab",
            "-northstar",
            "north_star",
            "northstar-",
            "north--star",
        ):
            with self.subTest(slug=invalid_slug), self.assertRaises(ValidationError):
                TenantSessionLoginRequest(
                    workspace_slug=invalid_slug,
                    email="person@example.com",
                    password="legacy",
                )

    def test_session_response_has_exact_public_shape(self) -> None:
        response = SessionPrincipalResponse(
            principal_type="platform_admin",
            principal_id=uuid.uuid4(),
            name="Platform Admin",
            email="admin@example.com",
            role="Platform Admin",
            tenant=None,
        )
        self.assertEqual(
            set(response.model_dump(mode="json")),
            {
                "principal_type",
                "principal_id",
                "name",
                "email",
                "role",
                "tenant",
            },
        )


class SessionSecurityTests(unittest.TestCase):
    def test_client_ip_uses_server_canonical_peer_not_untrusted_header(self) -> None:
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "scheme": "https",
                "path": "/auth/session/platform",
                "raw_path": b"/auth/session/platform",
                "query_string": b"",
                "headers": [(b"x-forwarded-for", b"198.51.100.99")],
                "client": ("203.0.113.10", 54321),
                "server": ("api.example.test", 443),
                "http_version": "1.1",
            }
        )

        self.assertEqual(auth_router._client_ip(request), "203.0.113.10")

    def test_secret_digest_is_stable_sha256_without_raw_value(self) -> None:
        raw = "a-sensitive-token"
        digest = digest_secret(raw)
        self.assertEqual(len(digest), 64)
        self.assertNotIn(raw, digest)
        self.assertEqual(digest, digest_secret(raw))

    def test_throttle_keys_do_not_persist_email(self) -> None:
        key = platform_account_throttle_key("Person@Example.com")
        self.assertEqual(len(key), 64)
        self.assertNotIn("person@example.com", key)

    def test_csrf_requires_cookie_header_match_and_session_binding(self) -> None:
        csrf = "csrf-token"
        session = SimpleNamespace(csrf_token_hash=digest_secret(csrf))
        self.assertTrue(browser_session_csrf_is_valid(session, csrf, csrf))
        self.assertFalse(browser_session_csrf_is_valid(session, csrf, "different"))
        self.assertFalse(browser_session_csrf_is_valid(session, None, csrf))
        self.assertFalse(
            browser_session_csrf_is_valid(
                SimpleNamespace(csrf_token_hash=digest_secret("another")),
                csrf,
                csrf,
            )
        )

    def test_session_cookie_is_http_only_and_csrf_cookie_is_readable(self) -> None:
        settings = Settings(_env_file=None, environment="development")
        principal = SessionPrincipalResponse(
            principal_type="platform_admin",
            principal_id=uuid.uuid4(),
            name="Admin",
            email="admin@example.com",
            role="Platform Admin",
            tenant=None,
        )
        result = BrowserAuthenticationResult(principal, "session-value", "csrf-value")
        response = Response()

        with patch.object(auth_router, "get_settings", return_value=settings):
            auth_router._set_browser_session_cookies(response, result)

        cookies = response.headers.getlist("set-cookie")
        session_cookie = next(cookie for cookie in cookies if cookie.startswith("mt_session="))
        csrf_cookie = next(cookie for cookie in cookies if cookie.startswith("mt_csrf="))
        self.assertIn("HttpOnly", session_cookie)
        self.assertNotIn("HttpOnly", csrf_cookie)
        self.assertIn("SameSite=lax", session_cookie)
        self.assertIn("Path=/", session_cookie)
        self.assertIn("Max-Age=3600", session_cookie)
        self.assertNotIn("Secure", session_cookie)

    def test_non_development_cookies_are_secure(self) -> None:
        settings = Settings(
            _env_file=None,
            environment="production",
            jwt_secret_key="x" * 32,
        )
        self.assertTrue(settings.secure_cookies)

    def test_auth_public_routes_are_explicit(self) -> None:
        self.assertIn(("POST", "/auth/session/platform"), PUBLIC_ROUTES)
        self.assertIn(("POST", "/auth/session/tenant"), PUBLIC_ROUTES)
        self.assertNotIn(("GET", "/auth/session"), PUBLIC_ROUTES)
        self.assertFalse(any(path == "/auth" for _, path in PUBLIC_ROUTES))


async def _collect_asgi_response(app, scope, receive_messages):
    sent = []
    messages = iter(receive_messages)

    async def receive():
        try:
            return next(messages)
        except StopIteration:
            return {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    await app(scope, receive, send)
    return sent


def _http_scope(path="/test", headers=None):
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers or [],
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1234),
        "root_path": "",
    }


class TransportMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_browser_session_persists_only_secret_digests(self) -> None:
        principal = SessionPrincipalResponse(
            principal_type="platform_admin",
            principal_id=uuid.uuid4(),
            name="Admin",
            email="admin@example.com",
            role="Platform Admin",
            tenant=None,
        )
        records = []
        fake_db = SimpleNamespace(
            add=records.append,
            commit=AsyncMock(),
        )

        result = await _create_browser_session(fake_db, principal)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].token_hash, digest_secret(result.session_token))
        self.assertEqual(records[0].csrf_token_hash, digest_secret(result.csrf_token))
        self.assertNotEqual(records[0].token_hash, result.session_token)
        fake_db.commit.assert_awaited_once()

    async def test_cookie_authenticated_unsafe_request_requires_csrf(self) -> None:
        session = SimpleNamespace(
            session_id=uuid.uuid4(),
            principal_type="platform_admin",
            principal_id=uuid.uuid4(),
            tenant_id=None,
            csrf_token_hash=digest_secret("csrf-value"),
        )
        fake_db = object()

        @asynccontextmanager
        async def fake_session_for():
            yield fake_db

        middleware = AuthenticationMiddleware(lambda scope, receive, send: None)
        request = Request(
            {
                **_http_scope("/projects", headers=[(b"cookie", b"mt_session=session-value")]),
                "method": "POST",
            }
        )
        call_next = AsyncMock(return_value=Response(status_code=204))

        with (
            patch.object(db_manager, "session_for", new=fake_session_for),
            patch(
                "app.auth.middleware.auth_service.get_active_browser_session",
                new=AsyncMock(return_value=session),
            ),
        ):
            response = await middleware.dispatch(request, call_next)

        self.assertEqual(response.status_code, 403)
        call_next.assert_not_awaited()

    async def test_cookie_session_supplies_uniform_claims_context(self) -> None:
        session = SimpleNamespace(
            session_id=uuid.uuid4(),
            principal_type="tenant_user",
            principal_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            csrf_token_hash=digest_secret("csrf-value"),
            last_seen_at=SimpleNamespace(),
        )
        fake_db = object()

        @asynccontextmanager
        async def fake_session_for():
            yield fake_db

        async def call_next(request):
            self.assertEqual(request.state.auth_method, "browser_session")
            self.assertEqual(request.state.jwt_claims["type"], "user")
            self.assertEqual(
                request.state.jwt_claims["tenant_id"],
                str(session.tenant_id),
            )
            return Response(status_code=204)

        middleware = AuthenticationMiddleware(lambda scope, receive, send: None)
        request = Request(
            {
                **_http_scope(
                    "/projects",
                    headers=[(b"cookie", b"mt_session=session-value")],
                ),
                "method": "GET",
            }
        )
        touch = AsyncMock()
        with (
            patch.object(db_manager, "session_for", new=fake_session_for),
            patch(
                "app.auth.middleware.auth_service.get_active_browser_session",
                new=AsyncMock(return_value=session),
            ),
            patch(
                "app.auth.middleware.auth_service.touch_browser_session",
                new=touch,
            ),
        ):
            response = await middleware.dispatch(request, call_next)

        self.assertEqual(response.status_code, 204)
        touch.assert_awaited_once_with(fake_db, session)

    async def test_declared_oversized_body_is_rejected_before_application(self) -> None:
        called = False

        async def downstream(scope, receive, send):
            nonlocal called
            called = True

        app = RequestSizeLimitMiddleware(downstream, max_body_bytes=8)
        sent = await _collect_asgi_response(
            app,
            _http_scope(headers=[(b"content-length", b"9")]),
            [{"type": "http.request", "body": b"123456789", "more_body": False}],
        )
        self.assertFalse(called)
        self.assertEqual(sent[0]["status"], 413)
        self.assertEqual(json.loads(sent[1]["body"]), {"detail": "Request body too large"})

    async def test_streamed_body_cannot_bypass_limit(self) -> None:
        async def downstream(scope, receive, send):
            while True:
                message = await receive()
                if not message.get("more_body", False):
                    break
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        app = RequestSizeLimitMiddleware(downstream, max_body_bytes=8)
        sent = await _collect_asgi_response(
            app,
            _http_scope(),
            [
                {"type": "http.request", "body": b"12345", "more_body": True},
                {"type": "http.request", "body": b"6789", "more_body": False},
            ],
        )
        self.assertEqual(sent[0]["status"], 413)

    async def test_security_headers_decorate_api_response(self) -> None:
        async def downstream(scope, receive, send):
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": b"{}"})

        with patch(
            "app.common.middleware.security_middleware.get_settings",
            return_value=Settings(_env_file=None, environment="development"),
        ):
            app = SecurityHeadersMiddleware(downstream)
        sent = await _collect_asgi_response(app, _http_scope(), [])
        headers = {key.decode().lower(): value.decode() for key, value in sent[0]["headers"]}
        self.assertEqual(headers["x-content-type-options"], "nosniff")
        self.assertEqual(headers["x-frame-options"], "DENY")
        self.assertIn("default-src 'none'", headers["content-security-policy"])
        self.assertNotIn("strict-transport-security", headers)


if __name__ == "__main__":
    unittest.main()
