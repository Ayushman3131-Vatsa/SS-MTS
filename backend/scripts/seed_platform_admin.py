"""Bootstrap the very first platform_admins row.

Administrator is "Seeded / self" in the role hierarchy — nothing in the API
creates one, since it's the only role with no creator above it. Run this
once per environment.

Usage: python -m scripts.seed_platform_admin --name "Jane Doe" --email jane@platform.io

The password is prompted without terminal echo so it is not exposed through
process arguments, command history, or process-inspection tools.
"""

import argparse
import asyncio
import getpass
import secrets
from typing import Annotated

from pydantic import EmailStr, Field, TypeAdapter, ValidationError
from sqlalchemy import select

from app.common.security import hash_password, normalize_email, validate_password
from app.common.db.session import db_manager
from app.auth.models.platform_admin import PlatformAdmin

_EMAIL_ADAPTER = TypeAdapter(Annotated[EmailStr, Field(max_length=254)])


def _prompt_for_password() -> str:
    password = getpass.getpass("Platform administrator password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if not secrets.compare_digest(password, confirmation):
        raise ValueError("Passwords do not match")
    return password


async def _seed(name: str, email: str, password: str) -> None:
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 255:
        raise ValueError("Name must contain between 1 and 255 non-whitespace characters")
    try:
        normalized_email = normalize_email(str(_EMAIL_ADAPTER.validate_python(email)))
    except ValidationError as exc:
        raise ValueError("A valid email address of at most 254 characters is required") from exc
    validate_password(password, email=normalized_email, name=normalized_name)

    async with db_manager.session_for() as session:
        existing = await session.scalar(
            select(PlatformAdmin).where(PlatformAdmin.email == normalized_email)
        )
        if existing is not None:
            raise ValueError("A platform administrator with this email already exists")

        admin = PlatformAdmin(
            name=normalized_name,
            email=normalized_email,
            password_hash=hash_password(password),
        )
        session.add(admin)
        await session.commit()
        print(f"Created platform admin {admin.admin_id} ({admin.email})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the first platform administrator")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    try:
        password = _prompt_for_password()
        asyncio.run(_seed(args.name, args.email, password))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
