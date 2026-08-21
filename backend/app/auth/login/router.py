from datetime import datetime, timedelta, timezone
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import Principal, get_current_principal
from app.common.config import get_settings
from app.common.db.session import get_db
from app.auth.login import service
from app.auth.schemas.auth import (
    AdminLoginRequest,
    PasswordChangeRequest,
    PasswordChangeResponse,
    PlatformSessionLoginRequest,
    SessionPrincipalResponse,
    TenantLoginRequest,
    TenantSessionLoginRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    # Deliberately do not trust X-Forwarded-For here. A deployment behind a
    # proxy should configure the ASGI server's trusted proxy handling so
    # request.client is canonical and cannot be spoofed by arbitrary clients.
    return request.client.host if request.client is not None else "unknown"


def _raise_rate_limit(exc: service.LoginRateLimitedError) -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=service.GENERIC_RATE_LIMIT_MESSAGE,
        headers={
            "Retry-After": str(exc.retry_after),
            "Cache-Control": "no-store",
        },
    ) from exc


def _mark_sensitive_response(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def _set_browser_session_cookies(
    response: Response,
    result: service.BrowserAuthenticationResult | service.PasswordChangeResult,
) -> None:
    if result.session_token is None or result.csrf_token is None:
        raise RuntimeError("Browser authentication result is missing cookie secrets")
    settings = get_settings()
    max_age = settings.browser_session_expire_minutes * 60
    expires = datetime.now(timezone.utc) + timedelta(seconds=max_age)
    common = {
        "max_age": max_age,
        "expires": expires,
        "path": "/",
        "secure": settings.secure_cookies,
        "samesite": "lax",
    }
    response.set_cookie(
        key=settings.session_cookie_name,
        value=result.session_token,
        httponly=True,
        **common,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=result.csrf_token,
        httponly=False,
        **common,
    )
    _mark_sensitive_response(response)


def _clear_browser_session_cookies(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.secure_cookies,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path="/",
        secure=settings.secure_cookies,
        httponly=False,
        samesite="lax",
    )
    _mark_sensitive_response(response)


@router.post("/admin/login", response_model=TokenResponse)
async def admin_login(
    payload: AdminLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Compatibility endpoint for non-browser bearer-token clients."""

    try:
        result = await service.login_platform_admin(
            db,
            payload,
            ip_address=_client_ip(request),
        )
    except service.LoginRateLimitedError as exc:
        _raise_rate_limit(exc)
    _mark_sensitive_response(response)
    return result


@router.post("/login", response_model=TokenResponse)
async def tenant_login(
    payload: TenantLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Compatibility endpoint for non-browser bearer-token clients."""

    try:
        result = await service.login_tenant_user(
            db,
            payload,
            ip_address=_client_ip(request),
        )
    except service.LoginRateLimitedError as exc:
        _raise_rate_limit(exc)
    _mark_sensitive_response(response)
    return result


@router.post("/session/platform", response_model=SessionPrincipalResponse)
async def platform_session_login(
    payload: PlatformSessionLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> SessionPrincipalResponse:
    try:
        result = await service.login_platform_browser(
            db,
            payload,
            ip_address=_client_ip(request),
        )
    except service.LoginRateLimitedError as exc:
        _raise_rate_limit(exc)
    _set_browser_session_cookies(response, result)
    return result.principal


@router.post("/session/tenant", response_model=SessionPrincipalResponse)
async def tenant_session_login(
    payload: TenantSessionLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> SessionPrincipalResponse:
    try:
        result = await service.login_tenant_browser(
            db,
            payload,
            ip_address=_client_ip(request),
        )
    except service.LoginRateLimitedError as exc:
        _raise_rate_limit(exc)
    _set_browser_session_cookies(response, result)
    return result.principal


@router.post("/password/change", response_model=PasswordChangeResponse)
async def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> PasswordChangeResponse:
    result = await service.change_tenant_password(
        db,
        principal,
        payload,
        auth_method=getattr(request.state, "auth_method", ""),
    )
    if result.session_token is not None:
        _set_browser_session_cookies(response, result)
    else:
        _mark_sensitive_response(response)
    return PasswordChangeResponse(
        principal=result.principal,
        replacement_access_token=result.replacement_access_token,
        token_type="bearer" if result.replacement_access_token is not None else None,
    )


@router.get("/session", response_model=SessionPrincipalResponse)
async def restore_session(
    response: Response,
    principal: Principal = Depends(get_current_principal),
    db: AsyncSession = Depends(get_db),
) -> SessionPrincipalResponse:
    _mark_sensitive_response(response)
    return await service.session_response_for_principal(db, principal)


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
async def logout_session(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> None:
    # The middleware sets this only after authenticating an opaque session.
    # A missing/expired cookie still reaches this route so logout is
    # idempotent and can always remove stale browser cookies.
    await service.revoke_browser_session(
        db,
        getattr(request.state, "browser_session_id", None),
    )
    _clear_browser_session_cookies(response)
