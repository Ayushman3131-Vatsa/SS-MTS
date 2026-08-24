"""Create the first Tenant Admin for a newly registered tenant."""

from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.email_identity import reserve_new_user_email
from app.auth.username_identity import allocate_unique_tenant_username
from app.auth.models.role import Role
from app.auth.models.user_account import UserAccount
from app.auth.models.user_role import UserRole
from app.auth.models.user_session import UserSession
from app.auth.roles import assign_role
from app.common.audit import record_audit
from app.common.exceptions import BusinessRuleError, NotFoundError
from app.common.security import hash_password, normalize_email, validate_password
from app.tenant_management.models.tenant import Tenant

_PASSWORD_LENGTH = 16
_SPECIAL = "!@#$%^&*()-_=+"


def generate_temporary_password(*, email: str, name: str, org_name: str) -> str:
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


async def create_first_tenant_admin(
    db: AsyncSession,
    *,
    tenant: Tenant,
    role: Role,
) -> tuple[str, str, str]:
    email = str(tenant.contact_email)
    await reserve_new_user_email(
        db,
        email,
        tenant_id=tenant.tenant_id,
        allow_tenant_primary_contact=True,
    )
    username = await allocate_unique_tenant_username(db, email)
    password = generate_temporary_password(
        email=email,
        name=tenant.contact_name,
        org_name=tenant.org_name,
    )
    admin = UserAccount(
        tenant_id=tenant.tenant_id,
        display_name=tenant.contact_name,
        username=username,
        email=email,
        password_hash=hash_password(password),
        created_by_user_id=None,
        is_active=True,
        force_pw_reset=True,
    )
    db.add(admin)
    await db.flush()
    await assign_role(db, user_id=admin.id, role=role, assigned_by=None)
    await record_audit(
        db,
        tenant_id=tenant.tenant_id,
        entity_type="user",
        entity_id=admin.id,
        action="BOOTSTRAP_TENANT_ADMIN",
        changed_by_user_id=None,
        new_value={
            "name": admin.display_name,
            "username": username,
            "email": email,
            "role": "Tenant Admin",
            "force_pw_reset": True,
        },
    )
    return email, username, password


async def rotate_pending_tenant_admin_password(
    db: AsyncSession,
    *,
    tenant: Tenant,
    changed_by_admin_id: uuid.UUID | None = None,
) -> tuple[str, str, str]:
    contact_email = normalize_email(str(tenant.contact_email))
    existing_admin = await db.scalar(
        select(UserAccount)
        .join(UserRole, UserRole.user_id == UserAccount.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            UserAccount.tenant_id == tenant.tenant_id,
            Role.role_code == "TENANT_ADMIN",
            UserRole.is_active.is_(True),
        )
        .limit(1)
    )
    if existing_admin is None:
        raise NotFoundError("No Tenant Admin found for this organization")
    if not existing_admin.force_pw_reset:
        raise BusinessRuleError(
            "The Tenant Admin has already set their password. Create or update a user from tenant access management instead."
        )
    if normalize_email(str(existing_admin.email)) != contact_email:
        raise BusinessRuleError(
            "The pending Tenant Admin does not match the primary contact email on this tenant."
        )

    password = generate_temporary_password(
        email=contact_email,
        name=tenant.contact_name,
        org_name=tenant.org_name,
    )
    now = datetime.now(timezone.utc)
    existing_admin.password_hash = hash_password(password)
    existing_admin.credential_version += 1
    existing_admin.failed_login_count = 0
    existing_admin.locked_until = None
    await db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == existing_admin.id,
            UserSession.revoked_at.is_(None),
        )
        .values(revoked_at=now, revoked_by="bootstrap_rotation")
    )
    await record_audit(
        db,
        tenant_id=tenant.tenant_id,
        entity_type="user",
        entity_id=existing_admin.id,
        action="ROTATE_BOOTSTRAP_PASSWORD",
        changed_by_user_id=None,
        changed_by_admin_id=changed_by_admin_id,
        new_value={"email": contact_email, "role": "Tenant Admin"},
    )
    return contact_email, str(existing_admin.username), password
