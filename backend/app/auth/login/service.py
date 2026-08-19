"""Authentication application service.

Bearer tokens remain available for API clients. Browser clients receive an
opaque random token whose SHA-256 digest is the only value persisted.

Account lockout uses ``failed_login_count`` / ``locked_until`` on
``platform_admins`` and ``user_accounts`` (no separate throttle table).
"""

from __future__ import annotations

import hashlib
import math
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import NoReturn

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import Principal
from app.auth.roles import get_active_role_name
from app.common.config import get_settings
from app.common.exceptions import UnauthorizedError
from app.common.security import (
    create_access_token,
    normalize_email,
    verify_password_and_update,
    verify_password_or_dummy,
)
from app.auth.models.platform_admin import PlatformAdmin
from app.tenant_management.models.tenant import Tenant
from app.auth.models.user_account import UserAccount
from app.auth.models.user_session import UserSession
from app.tenant_management.tenants import repository as tenant_repository
from app.auth.schemas.auth import (
    AdminLoginRequest,
    PlatformSessionLoginRequest,
    SessionOfferingResponse,
    SessionPrincipalResponse,
    SessionTenantResponse,
    TenantLoginRequest,
    TenantSessionLoginRequest,
    TokenResponse,
)

GENERIC_CREDENTIALS_MESSAGE = "Invalid credentials"
GENERIC_RATE_LIMIT_MESSAGE = "Unable to sign in. Please try again later."


class LoginRateLimitedError(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, retry_after)
        super().__init__(GENERIC_RATE_LIMIT_MESSAGE)


def _throttle_key(namespace: str, value: str) -> str:
    return digest_secret(f"{namespace}:{value}")


def ip_throttle_key(ip_address: str) -> str:
    return _throttle_key("ip", ip_address.strip() or "unknown")


def platform_account_throttle_key(email: str) -> str:
    return _throttle_key("account:platform", normalize_email(email))


def tenant_account_throttle_key(tenant_reference: str, email: str) -> str:
    return _throttle_key("account:tenant", f"{tenant_reference}:{normalize_email(email)}")


@dataclass(frozen=True)
class BrowserAuthenticationResult:
    principal: SessionPrincipalResponse
    session_token: str
    csrf_token: str


@dataclass(frozen=True)
class AuthStateCleanupResult:
    sessions_deleted: int
    throttle_rows_deleted: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _seconds_until(value: datetime, now: datetime) -> int:
    return max(1, math.ceil((_as_utc(value) - now).total_seconds()))


def digest_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _ensure_not_locked(locked_until: datetime | None, *, now: datetime) -> None:
    if locked_until is not None and _as_utc(locked_until) > now:
        raise LoginRateLimitedError(_seconds_until(locked_until, now))


async def _register_account_failure(
    db: AsyncSession,
    *,
    failed_login_count: int,
    now: datetime,
) -> tuple[int, datetime | None]:
    settings = get_settings()
    next_count = failed_login_count + 1
    locked_until = None
    if next_count >= settings.auth_account_failure_limit:
        locked_until = now + timedelta(minutes=settings.auth_lockout_minutes)
        next_count = 0
    return next_count, locked_until


async def _authentication_failed_anonymous() -> NoReturn:
    raise UnauthorizedError(GENERIC_CREDENTIALS_MESSAGE)


async def _authenticate_platform_admin(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    ip_address: str,
) -> PlatformAdmin:
    del ip_address  # reserved for future IP-level controls
    now = _utc_now()
    normalized_email = normalize_email(email)

    result = await db.execute(
        select(PlatformAdmin).where(PlatformAdmin.email == normalized_email).limit(1)
    )
    admin = result.scalar_one_or_none()
    if admin is None:
        verify_password_or_dummy(password, None)
        await _authentication_failed_anonymous()

    _ensure_not_locked(admin.locked_until, now=now)

    verified, replacement_hash = verify_password_and_update(password, admin.password_hash)
    if not verified:
        next_count, locked_until = await _register_account_failure(
            db, failed_login_count=admin.failed_login_count, now=now
        )
        admin.failed_login_count = next_count
        admin.locked_until = locked_until
        await db.commit()
        if locked_until is not None:
            raise LoginRateLimitedError(_seconds_until(locked_until, now))
        raise UnauthorizedError(GENERIC_CREDENTIALS_MESSAGE)

    if replacement_hash is not None:
        admin.password_hash = replacement_hash
    admin.failed_login_count = 0
    admin.locked_until = None
    admin.last_login_at = now
    return admin


async def _tenant_for_slug(
    db: AsyncSession,
    workspace_slug: str,
) -> Tenant | None:
    result = await db.execute(
        select(Tenant).where(Tenant.workspace_slug == workspace_slug).limit(1)
    )
    return result.scalar_one_or_none()


async def _authenticate_tenant_user(
    db: AsyncSession,
    *,
    tenant: Tenant | None,
    tenant_reference: str,
    email: str,
    password: str,
    ip_address: str,
) -> UserAccount:
    del tenant_reference, ip_address
    now = _utc_now()
    normalized_email = normalize_email(email)

    # Always execute the same account lookup, even for an unknown workspace,
    # so workspace existence does not create an obvious database fast path.
    lookup_tenant_id = tenant.tenant_id if tenant is not None else uuid.UUID(int=0)
    result = await db.execute(
        select(UserAccount)
        .where(UserAccount.tenant_id == lookup_tenant_id, UserAccount.email == normalized_email)
        .limit(1)
    )
    user: UserAccount | None = result.scalar_one_or_none()

    if user is None:
        verify_password_or_dummy(password, None)
        await _authentication_failed_anonymous()

    _ensure_not_locked(user.locked_until, now=now)

    verified, replacement_hash = verify_password_and_update(password, user.password_hash)
    if (
        not verified
        or not user.is_active
        or tenant is None
    ):
        next_count, locked_until = await _register_account_failure(
            db, failed_login_count=user.failed_login_count, now=now
        )
        user.failed_login_count = next_count
        user.locked_until = locked_until
        await db.commit()
        if locked_until is not None:
            raise LoginRateLimitedError(_seconds_until(locked_until, now))
        raise UnauthorizedError(GENERIC_CREDENTIALS_MESSAGE)

    if replacement_hash is not None:
        user.password_hash = replacement_hash
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    return user


def _platform_principal(admin: PlatformAdmin) -> SessionPrincipalResponse:
    return SessionPrincipalResponse(
        principal_type="platform_admin",
        principal_id=admin.admin_id,
        name=admin.name,
        email=str(admin.email),
        role="Platform Admin",
        tenant=None,
    )


async def _tenant_principal(
    db: AsyncSession,
    user: UserAccount,
    tenant: Tenant,
    role_name: str,
) -> SessionPrincipalResponse:
    offerings = await tenant_repository.list_tenant_offerings(db, tenant.tenant_id)
    return SessionPrincipalResponse(
        principal_type="tenant_user",
        principal_id=user.id,
        name=user.display_name,
        email=str(user.email),
        role=role_name,
        tenant=SessionTenantResponse(
            tenant_id=tenant.tenant_id,
            org_name=tenant.org_name,
            workspace_slug=tenant.workspace_slug,
            status=tenant.status,
            offerings=[
                SessionOfferingResponse.model_validate(offering)
                for offering in offerings
            ],
        ),
    )


async def _create_browser_session(
    db: AsyncSession,
    principal: SessionPrincipalResponse,
) -> BrowserAuthenticationResult:
    settings = get_settings()
    now = _utc_now()

    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    tenant_id = principal.tenant.tenant_id if principal.tenant is not None else None
    user_id = principal.principal_id if principal.principal_type == "tenant_user" else None
    db.add(
        UserSession(
            token_hash=digest_secret(session_token),
            csrf_token_hash=digest_secret(csrf_token),
            principal_type=principal.principal_type,
            principal_id=principal.principal_id,
            tenant_id=tenant_id,
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(minutes=settings.browser_session_expire_minutes),
            last_seen_at=now,
        )
    )
    await db.commit()
    return BrowserAuthenticationResult(
        principal=principal,
        session_token=session_token,
        csrf_token=csrf_token,
    )


async def login_platform_admin(
    db: AsyncSession,
    payload: AdminLoginRequest,
    *,
    ip_address: str = "unknown",
) -> TokenResponse:
    admin = await _authenticate_platform_admin(
        db,
        email=str(payload.email),
        password=payload.password,
        ip_address=ip_address,
    )
    await db.commit()
    token = create_access_token({"sub": str(admin.admin_id), "type": "admin"})
    return TokenResponse(access_token=token, role="Administrator", tenant_id=None)


async def login_tenant_user(
    db: AsyncSession,
    payload: TenantLoginRequest,
    *,
    ip_address: str = "unknown",
) -> TokenResponse:
    tenant = await db.get(Tenant, payload.tenant_id)
    user = await _authenticate_tenant_user(
        db,
        tenant=tenant,
        tenant_reference=str(payload.tenant_id),
        email=str(payload.email),
        password=payload.password,
        ip_address=ip_address,
    )
    role_name = await get_active_role_name(db, user.id)
    if role_name is None:
        raise UnauthorizedError(GENERIC_CREDENTIALS_MESSAGE)
    await db.commit()
    token = create_access_token(
        {
            "sub": str(user.id),
            "type": "user",
            "tenant_id": str(user.tenant_id),
            "role": role_name,
        }
    )
    return TokenResponse(access_token=token, role=role_name, tenant_id=user.tenant_id)


async def login_platform_browser(
    db: AsyncSession,
    payload: PlatformSessionLoginRequest,
    *,
    ip_address: str,
) -> BrowserAuthenticationResult:
    admin = await _authenticate_platform_admin(
        db,
        email=str(payload.email),
        password=payload.password,
        ip_address=ip_address,
    )
    return await _create_browser_session(db, _platform_principal(admin))


async def login_tenant_browser(
    db: AsyncSession,
    payload: TenantSessionLoginRequest,
    *,
    ip_address: str,
) -> BrowserAuthenticationResult:
    tenant = await _tenant_for_slug(db, payload.workspace_slug)
    tenant_reference = str(tenant.tenant_id) if tenant is not None else f"slug:{payload.workspace_slug}"
    user = await _authenticate_tenant_user(
        db,
        tenant=tenant,
        tenant_reference=tenant_reference,
        email=str(payload.email),
        password=payload.password,
        ip_address=ip_address,
    )
    if tenant is None:  # pragma: no cover - unreachable after authentication
        raise UnauthorizedError(GENERIC_CREDENTIALS_MESSAGE)
    role_name = await get_active_role_name(db, user.id)
    if role_name is None:
        raise UnauthorizedError(GENERIC_CREDENTIALS_MESSAGE)
    return await _create_browser_session(db, await _tenant_principal(db, user, tenant, role_name))


async def get_active_browser_session(
    db: AsyncSession,
    session_token: str,
) -> UserSession | None:
    if not session_token or len(session_token) > 256:
        return None
    now = _utc_now()
    result = await db.execute(
        select(UserSession)
        .where(
            UserSession.token_hash == digest_secret(session_token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


def browser_session_csrf_is_valid(
    session: UserSession,
    cookie_token: str | None,
    header_token: str | None,
) -> bool:
    if (
        not cookie_token
        or not header_token
        or len(cookie_token) > 256
        or len(header_token) > 256
        or not secrets.compare_digest(cookie_token, header_token)
    ):
        return False
    return secrets.compare_digest(digest_secret(header_token), session.csrf_token_hash)


async def touch_browser_session(db: AsyncSession, session: UserSession) -> None:
    now = _utc_now()
    if _as_utc(session.last_seen_at) > now - timedelta(minutes=5):
        return
    await db.execute(
        update(UserSession)
        .where(UserSession.id == session.id)
        .values(last_seen_at=now)
    )
    await db.commit()


async def revoke_browser_session(
    db: AsyncSession,
    session_id: uuid.UUID | None,
) -> None:
    if session_id is not None:
        await db.execute(
            update(UserSession)
            .where(
                UserSession.id == session_id,
                UserSession.revoked_at.is_(None),
            )
            .values(revoked_at=_utc_now())
        )
        await db.commit()


async def cleanup_expired_auth_state(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> AuthStateCleanupResult:
    cleanup_time = now or _utc_now()

    session_result = await db.execute(
        delete(UserSession).where(
            or_(
                UserSession.expires_at <= cleanup_time,
                UserSession.revoked_at.is_not(None),
            )
        )
    )
    await db.commit()
    return AuthStateCleanupResult(
        sessions_deleted=max(0, session_result.rowcount or 0),
        throttle_rows_deleted=0,
    )


async def session_response_for_principal(
    db: AsyncSession,
    principal: Principal,
) -> SessionPrincipalResponse:
    if principal.type == "admin":
        admin = await db.get(PlatformAdmin, principal.id)
        if admin is None:
            raise UnauthorizedError("Authentication required")
        return _platform_principal(admin)

    if principal.tenant_id is None:
        raise UnauthorizedError("Authentication required")
    user = await db.get(UserAccount, principal.id)
    tenant = await db.get(Tenant, principal.tenant_id)
    if (
        user is None
        or user.tenant_id != principal.tenant_id
        or not user.is_active
        or tenant is None
    ):
        raise UnauthorizedError("Authentication required")
    role_name = await get_active_role_name(db, user.id)
    if role_name is None:
        raise UnauthorizedError("Authentication required")
    return await _tenant_principal(db, user, tenant, role_name)
