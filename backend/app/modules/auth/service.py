"""Authentication application service.

Bearer tokens remain available for API clients. Browser clients receive an
opaque random token whose SHA-256 digest is the only value persisted. Login
throttles are also persisted, so limits are shared by every API worker.
"""

from __future__ import annotations

import hashlib
import math
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import NoReturn

from sqlalchemy import case, delete, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    normalize_email,
    verify_password_and_update,
    verify_password_or_dummy,
)
from app.models.auth_rate_limit import AuthRateLimit
from app.models.browser_session import BrowserSession
from app.models.platform_admin import PlatformAdmin
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.auth import (
    AdminLoginRequest,
    PlatformSessionLoginRequest,
    SessionPrincipalResponse,
    SessionOfferingResponse,
    SessionTenantResponse,
    TenantLoginRequest,
    TenantSessionLoginRequest,
    TokenResponse,
)
from app.modules.tenants import repository as tenant_repository

GENERIC_CREDENTIALS_MESSAGE = "Invalid credentials"
GENERIC_RATE_LIMIT_MESSAGE = "Unable to sign in. Please try again later."


class LoginRateLimitedError(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(1, retry_after)
        super().__init__(GENERIC_RATE_LIMIT_MESSAGE)


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


def _throttle_key(namespace: str, value: str) -> str:
    # Raw emails, tenant identifiers and IP addresses do not need to be kept
    # in the throttle table. The namespace prevents cross-purpose collisions.
    return digest_secret(f"{namespace}:{value}")


def ip_throttle_key(ip_address: str) -> str:
    return _throttle_key("ip", ip_address.strip() or "unknown")


def platform_account_throttle_key(email: str) -> str:
    return _throttle_key("account:platform", normalize_email(email))


def tenant_account_throttle_key(tenant_reference: str, email: str) -> str:
    return _throttle_key("account:tenant", f"{tenant_reference}:{normalize_email(email)}")


async def _retry_after_if_limited(
    db: AsyncSession,
    throttle_keys: tuple[str, ...],
    *,
    now: datetime,
) -> int | None:
    result = await db.execute(
        select(AuthRateLimit).where(AuthRateLimit.throttle_key.in_(throttle_keys))
    )
    retry_after = 0
    for throttle in result.scalars().all():
        if throttle.locked_until is not None and _as_utc(throttle.locked_until) > now:
            retry_after = max(retry_after, _seconds_until(throttle.locked_until, now))
    return retry_after or None


async def _ensure_login_allowed(
    db: AsyncSession,
    account_key: str,
    ip_key: str,
    *,
    now: datetime,
) -> None:
    retry_after = await _retry_after_if_limited(db, (account_key, ip_key), now=now)
    if retry_after is not None:
        raise LoginRateLimitedError(retry_after)


async def _upsert_login_failure(
    db: AsyncSession,
    throttle_key: str,
    *,
    threshold: int,
    now: datetime,
) -> datetime | None:
    """Atomically increment one throttle row using PostgreSQL ON CONFLICT."""

    settings = get_settings()
    window_cutoff = now - timedelta(minutes=settings.auth_rate_limit_window_minutes)
    new_lock_until = now + timedelta(minutes=settings.auth_lockout_minutes)

    window_expired = AuthRateLimit.window_started_at <= window_cutoff
    next_failures = case(
        (window_expired, 1),
        else_=AuthRateLimit.failures + 1,
    )
    next_locked_until = case(
        (window_expired, new_lock_until if threshold <= 1 else None),
        (next_failures >= threshold, new_lock_until),
        else_=AuthRateLimit.locked_until,
    )

    statement = (
        postgresql_insert(AuthRateLimit)
        .values(
            throttle_key=throttle_key,
            failures=1,
            window_started_at=now,
            locked_until=new_lock_until if threshold <= 1 else None,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=[AuthRateLimit.throttle_key],
            set_={
                "failures": next_failures,
                "window_started_at": case(
                    (window_expired, now),
                    else_=AuthRateLimit.window_started_at,
                ),
                "locked_until": next_locked_until,
                "updated_at": now,
            },
        )
        .returning(AuthRateLimit.locked_until)
    )
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def _register_login_failure(
    db: AsyncSession,
    account_key: str,
    ip_key: str,
    *,
    now: datetime,
) -> int | None:
    settings = get_settings()
    account_locked_until = await _upsert_login_failure(
        db,
        account_key,
        threshold=settings.auth_account_failure_limit,
        now=now,
    )
    ip_locked_until = await _upsert_login_failure(
        db,
        ip_key,
        threshold=settings.auth_ip_failure_limit,
        now=now,
    )
    await db.commit()

    locked_values = [
        value
        for value in (account_locked_until, ip_locked_until)
        if value is not None and _as_utc(value) > now
    ]
    if not locked_values:
        return None
    return max(_seconds_until(value, now) for value in locked_values)


async def _clear_account_failures(db: AsyncSession, account_key: str) -> None:
    await db.execute(delete(AuthRateLimit).where(AuthRateLimit.throttle_key == account_key))


async def _authentication_failed(
    db: AsyncSession,
    account_key: str,
    ip_key: str,
    *,
    now: datetime,
) -> NoReturn:
    retry_after = await _register_login_failure(db, account_key, ip_key, now=now)
    if retry_after is not None:
        raise LoginRateLimitedError(retry_after)
    raise UnauthorizedError(GENERIC_CREDENTIALS_MESSAGE)


async def _authenticate_platform_admin(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    ip_address: str,
) -> PlatformAdmin:
    now = _utc_now()
    normalized_email = normalize_email(email)
    account_key = platform_account_throttle_key(normalized_email)
    ip_key = ip_throttle_key(ip_address)
    await _ensure_login_allowed(db, account_key, ip_key, now=now)

    result = await db.execute(
        select(PlatformAdmin).where(PlatformAdmin.email == normalized_email).limit(1)
    )
    admin = result.scalar_one_or_none()
    if admin is None:
        verify_password_or_dummy(password, None)
        await _authentication_failed(db, account_key, ip_key, now=now)

    verified, replacement_hash = verify_password_and_update(password, admin.password_hash)
    if not verified:
        await _authentication_failed(db, account_key, ip_key, now=now)

    if replacement_hash is not None:
        admin.password_hash = replacement_hash
    await _clear_account_failures(db, account_key)
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
) -> User:
    now = _utc_now()
    normalized_email = normalize_email(email)
    account_key = tenant_account_throttle_key(tenant_reference, normalized_email)
    ip_key = ip_throttle_key(ip_address)
    await _ensure_login_allowed(db, account_key, ip_key, now=now)

    # Always execute the same account lookup, even for an unknown workspace,
    # so workspace existence does not create an obvious database fast path.
    lookup_tenant_id = tenant.tenant_id if tenant is not None else uuid.UUID(int=0)
    result = await db.execute(
        select(User)
        .where(User.tenant_id == lookup_tenant_id, User.email == normalized_email)
        .limit(1)
    )
    user: User | None = result.scalar_one_or_none()

    if user is None:
        verify_password_or_dummy(password, None)
        await _authentication_failed(db, account_key, ip_key, now=now)

    verified, replacement_hash = verify_password_and_update(password, user.password_hash)
    if (
        not verified
        or user.status != "Active"
        or tenant is None
    ):
        await _authentication_failed(db, account_key, ip_key, now=now)

    if replacement_hash is not None:
        user.password_hash = replacement_hash
    await _clear_account_failures(db, account_key)
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
    user: User,
    tenant: Tenant,
) -> SessionPrincipalResponse:
    offerings = await tenant_repository.list_tenant_offerings(db, tenant.tenant_id)
    return SessionPrincipalResponse(
        principal_type="tenant_user",
        principal_id=user.user_id,
        name=user.name,
        email=str(user.email),
        role=user.role,
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

    # token_urlsafe(32) is backed by 32 bytes (256 bits) from the OS CSPRNG.
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    tenant_id = principal.tenant.tenant_id if principal.tenant is not None else None
    db.add(
        BrowserSession(
            token_hash=digest_secret(session_token),
            csrf_token_hash=digest_secret(csrf_token),
            principal_type=principal.principal_type,
            principal_id=principal.principal_id,
            tenant_id=tenant_id,
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
    await db.commit()
    token = create_access_token(
        {
            "sub": str(user.user_id),
            "type": "user",
            "tenant_id": str(user.tenant_id),
            "role": user.role,
        }
    )
    return TokenResponse(access_token=token, role=user.role, tenant_id=user.tenant_id)


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
    # A successful authentication implies tenant is non-null, but the explicit
    # guard keeps the invariant visible to static type checkers and reviewers.
    if tenant is None:  # pragma: no cover - unreachable after authentication
        raise UnauthorizedError(GENERIC_CREDENTIALS_MESSAGE)
    return await _create_browser_session(db, await _tenant_principal(db, user, tenant))


async def get_active_browser_session(
    db: AsyncSession,
    session_token: str,
) -> BrowserSession | None:
    # Cap untrusted cookie input before hashing it. Legitimate tokens are only
    # 43 characters; the larger bound leaves room for encoding changes.
    if not session_token or len(session_token) > 256:
        return None
    now = _utc_now()
    result = await db.execute(
        select(BrowserSession)
        .where(
            BrowserSession.token_hash == digest_secret(session_token),
            BrowserSession.revoked_at.is_(None),
            BrowserSession.expires_at > now,
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


def browser_session_csrf_is_valid(
    session: BrowserSession,
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


async def touch_browser_session(db: AsyncSession, session: BrowserSession) -> None:
    now = _utc_now()
    if _as_utc(session.last_seen_at) > now - timedelta(minutes=5):
        return
    await db.execute(
        update(BrowserSession)
        .where(BrowserSession.session_id == session.session_id)
        .values(last_seen_at=now)
    )
    await db.commit()


async def revoke_browser_session(
    db: AsyncSession,
    session_id: uuid.UUID | None,
) -> None:
    if session_id is not None:
        await db.execute(
            update(BrowserSession)
            .where(
                BrowserSession.session_id == session_id,
                BrowserSession.revoked_at.is_(None),
            )
            .values(revoked_at=_utc_now())
        )
        await db.commit()


async def cleanup_expired_auth_state(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> AuthStateCleanupResult:
    """Delete unusable sessions and stale throttle counters.

    This is intentionally an explicit maintenance operation rather than work
    performed during login. Deployments can schedule the accompanying CLI
    without adding latency or lock contention to authentication requests.
    """

    cleanup_time = now or _utc_now()
    settings = get_settings()
    throttle_cutoff = cleanup_time - timedelta(
        minutes=max(
            settings.auth_rate_limit_window_minutes,
            settings.auth_lockout_minutes,
        )
    )

    session_result = await db.execute(
        delete(BrowserSession).where(
            or_(
                BrowserSession.expires_at <= cleanup_time,
                BrowserSession.revoked_at.is_not(None),
            )
        )
    )
    throttle_result = await db.execute(
        delete(AuthRateLimit).where(
            AuthRateLimit.updated_at <= throttle_cutoff,
            or_(
                AuthRateLimit.locked_until.is_(None),
                AuthRateLimit.locked_until <= cleanup_time,
            ),
        )
    )
    await db.commit()
    return AuthStateCleanupResult(
        sessions_deleted=max(0, session_result.rowcount or 0),
        throttle_rows_deleted=max(0, throttle_result.rowcount or 0),
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
    user = await db.get(
        User,
        {"tenant_id": principal.tenant_id, "user_id": principal.id},
    )
    tenant = await db.get(Tenant, principal.tenant_id)
    if (
        user is None
        or user.status != "Active"
        or tenant is None
    ):
        raise UnauthorizedError("Authentication required")
    return await _tenant_principal(db, user, tenant)
