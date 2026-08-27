"""Tenant-scoped tenant-user email reservation helpers.

Work email is optional. When present, it must be unique within the tenant.
Username remains globally unique and is always a valid sign-in identifier.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models.user_account import UserAccount
from app.common.exceptions import ConflictError
from app.common.security import normalize_email
from app.tenant_management.models.tenant import Tenant


async def lock_email_identity(db: AsyncSession, email: str) -> str:
    normalized = normalize_email(email)
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:email, 2))"),
        {"email": normalized},
    )
    return normalized


async def get_user_by_tenant_email(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    email: str,
) -> UserAccount | None:
    result = await db.execute(
        select(UserAccount).where(
            UserAccount.tenant_id == tenant_id,
            UserAccount.email == normalize_email(email),
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> UserAccount | None:
    result = await db.execute(
        select(UserAccount).where(UserAccount.email == normalize_email(email)).limit(1)
    )
    return result.scalar_one_or_none()


async def get_contact_tenant_by_email(db: AsyncSession, email: str) -> Tenant | None:
    result = await db.execute(
        select(Tenant).where(Tenant.contact_email == normalize_email(email)).limit(1)
    )
    return result.scalar_one_or_none()


async def reserve_new_tenant_contact(db: AsyncSession, email: str) -> str:
    normalized = await lock_email_identity(db, email)
    if await get_contact_tenant_by_email(db, normalized) is not None:
        raise ConflictError("This primary contact email is already reserved by another tenant")
    return normalized


async def reserve_new_user_email(
    db: AsyncSession,
    email: str,
    *,
    tenant_id: uuid.UUID,
    allow_tenant_primary_contact: bool = False,
) -> str:
    normalized = await lock_email_identity(db, email)
    if await get_user_by_tenant_email(db, tenant_id, normalized) is not None:
        raise ConflictError("A tenant user with this email already exists")

    contact_tenant = await get_contact_tenant_by_email(db, normalized)
    if contact_tenant is not None and contact_tenant.tenant_id == tenant_id and not allow_tenant_primary_contact:
        raise ConflictError("This email is reserved as a tenant primary contact")
    return normalized
