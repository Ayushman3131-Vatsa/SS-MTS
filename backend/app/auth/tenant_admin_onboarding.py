"""First Tenant Admin provisioning shared by the API and operational CLI."""

from __future__ import annotations

import secrets
import string
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.tenant.defaults import ensure_system_role_page_defaults
from app.auth.email_identity import lock_email_identity, reserve_new_user_email
from app.auth.username_identity import allocate_unique_tenant_username
from app.auth.models.role import Role
from app.auth.models.system_roles import SYSTEM_ROLES
from app.auth.models.user_account import UserAccount
from app.auth.models.user_role import UserRole
from app.auth.models.user_session import UserSession
from app.auth.roles import assign_role
from app.common.audit import record_audit
from app.common.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.common.security import hash_password, normalize_email, validate_password
from app.tenant_management.models.tenant import Tenant
from app.tenant_management.models.platform_activity_event import PlatformActivityEvent
from app.tenant_management.models.enums import PlatformActivityType, PlatformActorType

_PASSWORD_LENGTH = 20
_SPECIAL = "!@#$%^&*()-_="


@dataclass(frozen=True)
class InitialTenantAdminCredentials:
    email: str
    temporary_password: str


def generate_temporary_password(*, email: str, name: str, org_name: str) -> str:
    """Generate a password that satisfies the application's current policy."""
    alphabet = string.ascii_letters + string.digits + _SPECIAL
    random = secrets.SystemRandom()
    while True:
        characters = [
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.digits),
            secrets.choice(_SPECIAL),
        ]
        characters.extend(secrets.choice(alphabet) for _ in range(_PASSWORD_LENGTH - 4))
        random.shuffle(characters)
        password = "".join(characters)
        try:
            validate_password(password, email=email, name=name, org_name=org_name)
        except ValueError:
            continue
        return password


async def _tenant_or_404_for_update(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    result = await db.execute(
        select(Tenant).where(Tenant.tenant_id == tenant_id).with_for_update()
    )
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise NotFoundError("Tenant not found", code="TENANT_NOT_FOUND")
    return tenant


async def _ensure_system_roles(db: AsyncSession, tenant_id: uuid.UUID) -> dict[str, Role]:
    """Create any missing canonical roles and reactivate canonical disabled ones."""
    result = await db.execute(select(Role).where(Role.tenant_id == tenant_id))
    roles_by_code = {role.role_code: role for role in result.scalars()}
    for role_code, role_name in SYSTEM_ROLES:
        role = roles_by_code.get(role_code)
        if role is None:
            role = Role(
                tenant_id=tenant_id,
                role_code=role_code,
                role_name=role_name,
                description=f"System role: {role_name}",
                is_system=True,
                is_active=True,
            )
            db.add(role)
            roles_by_code[role_code] = role
        else:
            role.role_name = role_name
            role.is_system = True
            role.is_active = True
    await db.flush()
    return roles_by_code


async def _first_tenant_admin(db: AsyncSession, tenant_id: uuid.UUID) -> UserAccount | None:
    result = await db.execute(
        select(UserAccount)
        .join(UserRole, UserRole.user_id == UserAccount.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            UserAccount.tenant_id == tenant_id,
            Role.role_code == "TENANT_ADMIN",
            Role.is_active.is_(True),
            UserRole.is_active.is_(True),
        )
        .order_by(UserAccount.created_at, UserAccount.id)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _database_now(db: AsyncSession) -> datetime:
    now = await db.scalar(select(func.now()))
    if now is None:  # pragma: no cover - PostgreSQL always returns a value
        return datetime.now(timezone.utc)
    return now


async def enable_initial_tenant_admin(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    platform_admin_id: uuid.UUID | None,
    expected_version: int,
    idempotency_key: str,
) -> InitialTenantAdminCredentials:
    """Provision the primary contact as the tenant's first administrator."""
    tenant = await _tenant_or_404_for_update(db, tenant_id)
    if tenant.version != expected_version:
        raise ConflictError(
            "Tenant was modified by someone else — refresh and retry",
            code="TENANT_VERSION_CONFLICT",
        )

    existing_action = await db.scalar(
        select(PlatformActivityEvent).where(
            PlatformActivityEvent.idempotency_key == idempotency_key
        )
    )
    if existing_action is not None:
        raise ConflictError(
            "This enable request was already processed. Reload the tenant before continuing.",
            code="TENANT_ENABLE_ALREADY_PROCESSED",
        )

    contact_email = await lock_email_identity(db, str(tenant.contact_email))
    existing_admin = await _first_tenant_admin(db, tenant.tenant_id)
    if existing_admin is not None:
        raise BusinessRuleError(
            "The first Tenant Admin already exists",
            code="TENANT_ADMIN_ALREADY_EXISTS",
        )

    roles = await _ensure_system_roles(db, tenant.tenant_id)
    await ensure_system_role_page_defaults(db, tenant.tenant_id)
    password = generate_temporary_password(
        email=contact_email,
        name=tenant.contact_name,
        org_name=tenant.org_name,
    )
    await reserve_new_user_email(
        db,
        contact_email,
        tenant_id=tenant.tenant_id,
        allow_tenant_primary_contact=True,
    )
    username = await allocate_unique_tenant_username(db, contact_email)
    admin = UserAccount(
        tenant_id=tenant.tenant_id,
        display_name=tenant.contact_name,
        username=username,
        email=contact_email,
        password_hash=hash_password(password),
        created_by_user_id=None,
        is_active=True,
        force_pw_reset=True,
    )
    db.add(admin)
    await db.flush()
    await assign_role(db, user_id=admin.id, role=roles["TENANT_ADMIN"], assigned_by=None)

    now = await _database_now(db)
    tenant.version += 1
    tenant.updated_at = now
    await record_audit(
        db,
        tenant_id=tenant.tenant_id,
        entity_type="user",
        entity_id=admin.id,
        action="BOOTSTRAP_TENANT_ADMIN",
        changed_by_user_id=None,
        changed_by_admin_id=platform_admin_id,
        new_value={
            "name": admin.display_name,
            "username": username,
            "email": contact_email,
            "role": "Tenant Admin",
            "force_pw_reset": True,
        },
    )
    db.add(
        PlatformActivityEvent(
            event_type=PlatformActivityType.TENANT_ADMIN_ENABLED.value,
            tenant_id=tenant.tenant_id,
            tenant_name_snapshot=tenant.org_name,
            actor_id=platform_admin_id,
            actor_type=(
                PlatformActorType.PLATFORM_ADMIN.value
                if platform_admin_id is not None
                else PlatformActorType.SYSTEM.value
            ),
            occurred_at=now,
            event_metadata={"email": contact_email},
            idempotency_key=idempotency_key,
        )
    )
    await db.commit()
    return InitialTenantAdminCredentials(contact_email, password)


async def regenerate_initial_tenant_admin_password(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    platform_admin_id: uuid.UUID | None,
    expected_version: int,
    idempotency_key: str,
) -> InitialTenantAdminCredentials:
    """Rotate a lost bootstrap password before the tenant admin completes setup."""
    tenant = await _tenant_or_404_for_update(db, tenant_id)
    if tenant.version != expected_version:
        raise ConflictError(
            "Tenant was modified by someone else — refresh and retry",
            code="TENANT_VERSION_CONFLICT",
        )

    existing_action = await db.scalar(
        select(PlatformActivityEvent).where(
            PlatformActivityEvent.idempotency_key == idempotency_key
        )
    )
    if existing_action is not None:
        raise ConflictError(
            "This password regeneration request was already processed. Reload the tenant before continuing.",
            code="TENANT_PASSWORD_REGENERATION_ALREADY_PROCESSED",
        )

    contact_email = await lock_email_identity(db, str(tenant.contact_email))
    admin = await _first_tenant_admin(db, tenant.tenant_id)
    if admin is None:
        raise BusinessRuleError(
            "Enable the tenant before generating an initial password",
            code="TENANT_ADMIN_NOT_ENABLED",
        )
    if not admin.force_pw_reset:
        raise BusinessRuleError(
            "The Tenant Admin has already completed password setup",
            code="TENANT_ADMIN_ALREADY_ENABLED",
        )
    if normalize_email(str(admin.email)) != contact_email:
        raise BusinessRuleError(
            "The pending Tenant Admin does not match the primary contact",
            code="TENANT_ADMIN_CONTACT_MISMATCH",
        )

    password = generate_temporary_password(
        email=contact_email,
        name=tenant.contact_name,
        org_name=tenant.org_name,
    )
    now = await _database_now(db)
    admin.password_hash = hash_password(password)
    admin.credential_version += 1
    admin.failed_login_count = 0
    admin.locked_until = None
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == admin.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now, revoked_by="bootstrap_rotation")
    )
    tenant.version += 1
    tenant.updated_at = now
    await record_audit(
        db,
        tenant_id=tenant.tenant_id,
        entity_type="user",
        entity_id=admin.id,
        action="ROTATE_BOOTSTRAP_PASSWORD",
        changed_by_user_id=None,
        changed_by_admin_id=platform_admin_id,
        new_value={"email": contact_email, "role": "Tenant Admin"},
    )
    db.add(
        PlatformActivityEvent(
            event_type=PlatformActivityType.TENANT_ADMIN_PASSWORD_REGENERATED.value,
            tenant_id=tenant.tenant_id,
            tenant_name_snapshot=tenant.org_name,
            actor_id=platform_admin_id,
            actor_type=(
                PlatformActorType.PLATFORM_ADMIN.value
                if platform_admin_id is not None
                else PlatformActorType.SYSTEM.value
            ),
            occurred_at=now,
            event_metadata={"email": contact_email},
            idempotency_key=idempotency_key,
        )
    )
    await db.commit()
    return InitialTenantAdminCredentials(contact_email, password)
