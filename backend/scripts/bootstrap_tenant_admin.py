"""Create the first Tenant Admin from a tenant's primary contact.

Usage:
    python -m scripts.bootstrap_tenant_admin --tenant-code ACME

The UAM-owned TENANT_ADMIN role must already exist and be active. The
temporary password is generated locally, stored only as a hash, and printed
once after the transaction commits.
"""

from __future__ import annotations

import argparse
import asyncio
import secrets
import string
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.auth.email_identity import lock_email_identity, reserve_new_user_email
from app.auth.username_identity import allocate_unique_tenant_username
from app.auth.models.role import Role
from app.auth.models.user_account import UserAccount
from app.auth.models.user_role import UserRole
from app.auth.models.user_session import UserSession
from app.auth.roles import assign_role
from app.common.audit import record_audit
from app.common.db.session import db_manager
from app.common.security import hash_password, normalize_email, validate_password
from app.tenant_management.models.tenant import Tenant

_PASSWORD_LENGTH = 20
_SPECIAL = "!@#$%^&*()-_=+"


def _generate_temporary_password(*, email: str, name: str, org_name: str) -> str:
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


async def _bootstrap(tenant_code: str, *, rotate_pending: bool) -> tuple[str, str]:
    normalized_code = tenant_code.strip().upper()
    async with db_manager.session_for() as session:
        tenant = await session.scalar(
            select(Tenant).where(Tenant.tenant_code == normalized_code).with_for_update()
        )
        if tenant is None:
            raise ValueError(f"Tenant '{normalized_code}' was not found")

        role = await session.scalar(
            select(Role).where(
                Role.tenant_id == tenant.tenant_id,
                Role.role_code == "TENANT_ADMIN",
                Role.is_active.is_(True),
            )
        )
        if role is None:
            raise ValueError(
                "Active TENANT_ADMIN role is missing; provision it through UAM first"
            )

        contact_email = normalize_email(str(tenant.contact_email))
        await lock_email_identity(session, contact_email)
        existing_admin = await session.scalar(
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

        password = _generate_temporary_password(
            email=contact_email,
            name=tenant.contact_name,
            org_name=tenant.org_name,
        )
        if existing_admin is not None:
            if not rotate_pending:
                raise ValueError("A Tenant Admin already exists for this tenant")
            if not existing_admin.force_pw_reset:
                raise ValueError("The existing Tenant Admin has completed password setup")
            if normalize_email(str(existing_admin.email)) != contact_email:
                raise ValueError("Pending Tenant Admin does not match the primary contact")

            existing_admin.password_hash = hash_password(password)
            existing_admin.credential_version += 1
            existing_admin.failed_login_count = 0
            existing_admin.locked_until = None
            await session.execute(
                update(UserSession)
                .where(
                    UserSession.user_id == existing_admin.id,
                    UserSession.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(timezone.utc), revoked_by="bootstrap_rotation")
            )
            await record_audit(
                session,
                tenant_id=tenant.tenant_id,
                entity_type="user",
                entity_id=existing_admin.id,
                action="ROTATE_BOOTSTRAP_PASSWORD",
                changed_by_user_id=None,
                new_value={"email": contact_email, "role": "Tenant Admin"},
            )
        else:
            await reserve_new_user_email(
                session,
                contact_email,
                tenant_id=tenant.tenant_id,
                allow_tenant_primary_contact=True,
            )
            username = await allocate_unique_tenant_username(session, contact_email)
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
            session.add(admin)
            await session.flush()
            await assign_role(session, user_id=admin.id, role=role, assigned_by=None)
            await record_audit(
                session,
                tenant_id=tenant.tenant_id,
                entity_type="user",
                entity_id=admin.id,
                action="BOOTSTRAP_TENANT_ADMIN",
                changed_by_user_id=None,
                new_value={
                    "name": admin.display_name,
                    "email": contact_email,
                    "role": "Tenant Admin",
                    "force_pw_reset": True,
                },
            )

        await session.commit()
        return contact_email, password


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap a tenant's first administrator")
    parser.add_argument("--tenant-code", required=True)
    parser.add_argument(
        "--rotate-pending",
        action="store_true",
        help="Replace the password only for an existing reset-required Tenant Admin",
    )
    args = parser.parse_args()
    try:
        email, password = asyncio.run(
            _bootstrap(args.tenant_code, rotate_pending=args.rotate_pending)
        )
    except ValueError as exc:
        parser.error(str(exc))

    print(f"Tenant Admin: {email}")
    print(f"Temporary password: {password}")
    print("The user must change this password before accessing tenant features.")


if __name__ == "__main__":
    main()
