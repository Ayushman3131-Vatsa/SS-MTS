"""Globally unique tenant/platform usernames used as an alternate login identifier."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models.platform_user import PlatformAdmin
from app.auth.models.user_account import UserAccount
from app.common.exceptions import ConflictError

USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._-]{2,49}$")
USERNAME_TAKEN = "This username is already taken. Choose a different one."


def parse_username(value: str) -> str:
    stripped = value.strip()
    if "@" in stripped:
        raise ValueError("Username cannot be an email address")
    if not USERNAME_PATTERN.fullmatch(stripped):
        raise ValueError(
            "Username must be 3–50 characters, start with a letter, and use only "
            "letters, numbers, dots, hyphens, or underscores"
        )
    return stripped


def username_base_from_email(email: str) -> str:
    local = email.split("@", 1)[0]
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "", local).strip("._-")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"user{re.sub(r'[^A-Za-z0-9]', '', cleaned)}"
    if not cleaned or not cleaned[0].isalpha():
        cleaned = "user"
    if len(cleaned) < 3:
        cleaned = (cleaned + "xxx")[:3]
    return cleaned[:50]


async def lock_username(db: AsyncSession, username: str) -> str:
    normalized = parse_username(username)
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:username, 3))"),
        {"username": normalized.casefold()},
    )
    return normalized


async def get_tenant_user_by_username(db: AsyncSession, username: str) -> UserAccount | None:
    result = await db.execute(
        select(UserAccount).where(UserAccount.username == parse_username(username)).limit(1)
    )
    return result.scalar_one_or_none()


async def get_platform_admin_by_username(db: AsyncSession, username: str) -> PlatformAdmin | None:
    result = await db.execute(
        select(PlatformAdmin).where(PlatformAdmin.username == parse_username(username)).limit(1)
    )
    return result.scalar_one_or_none()


async def reserve_tenant_username(
    db: AsyncSession,
    username: str,
    *,
    exclude_user_id: uuid.UUID | None = None,
) -> str:
    normalized = await lock_username(db, username)
    existing = await get_tenant_user_by_username(db, normalized)
    if existing is not None and existing.id != exclude_user_id:
        raise ConflictError(USERNAME_TAKEN)
    return normalized


async def reserve_platform_username(
    db: AsyncSession,
    username: str,
    *,
    exclude_admin_id: uuid.UUID | None = None,
) -> str:
    normalized = await lock_username(db, username)
    existing = await get_platform_admin_by_username(db, normalized)
    if existing is not None and existing.admin_id != exclude_admin_id:
        raise ConflictError(USERNAME_TAKEN)
    return normalized


async def allocate_unique_tenant_username(db: AsyncSession, email: str) -> str:
    base = username_base_from_email(email)
    candidate = base
    suffix = 2
    while True:
        try:
            return await reserve_tenant_username(db, candidate)
        except (ConflictError, ValueError):
            extra = str(suffix)
            candidate = f"{base[: max(1, 50 - len(extra))]}{extra}"
            suffix += 1
            if suffix > 10_000:
                raise ConflictError("Could not allocate a unique username")
