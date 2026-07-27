"""Small ASGI security middleware with no framework-private dependencies."""

from __future__ import annotations

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings


class _RequestBodyTooLarge(Exception):
    pass


class RequestSizeLimitMiddleware:
    """Reject oversized fixed-length and streamed request bodies.

    The wrapped ``receive`` guards chunked requests too, so omitting
    Content-Length cannot bypass the limit.
    """

    def __init__(self, app: ASGIApp, max_body_bytes: int | None = None):
        self.app = app
        self.max_body_bytes = max_body_bytes or get_settings().max_request_body_bytes

    async def _respond(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        status_code: int,
        detail: str,
    ) -> None:
        await JSONResponse(
            status_code=status_code,
            content={"detail": detail},
        )(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        content_length = Headers(scope=scope).get("content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                await self._respond(
                    scope,
                    receive,
                    send,
                    status_code=400,
                    detail="Invalid Content-Length header",
                )
                return
            if declared_length < 0:
                await self._respond(
                    scope,
                    receive,
                    send,
                    status_code=400,
                    detail="Invalid Content-Length header",
                )
                return
            if declared_length > self.max_body_bytes:
                await self._respond(
                    scope,
                    receive,
                    send,
                    status_code=413,
                    detail="Request body too large",
                )
                return

        consumed = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > self.max_body_bytes:
                    raise _RequestBodyTooLarge
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _RequestBodyTooLarge:
            if response_started:
                raise
            await self._respond(
                scope,
                receive,
                send,
                status_code=413,
                detail="Request body too large",
            )


class SecurityHeadersMiddleware:
    _API_CSP = (
        "default-src 'none'; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'none'"
    )
    _DOCS_CSP = (
        "default-src 'self'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net"
    )

    def __init__(self, app: ASGIApp):
        self.app = app
        self.enable_hsts = not get_settings().is_development

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))
        docs_response = path in {"/docs", "/docs/", "/docs/oauth2-redirect", "/redoc"}

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = (
                    self._DOCS_CSP if docs_response else self._API_CSP
                )
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = (
                    "camera=(), geolocation=(), microphone=(), payment=(), usb=()"
                )
                headers["Cross-Origin-Opener-Policy"] = "same-origin"
                headers["Cross-Origin-Resource-Policy"] = "same-origin"
                if self.enable_hsts:
                    headers["Strict-Transport-Security"] = (
                        "max-age=31536000; includeSubDomains"
                    )
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
