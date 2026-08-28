"""Bootstrap the first platform administrator and its system role.

Administrator is "Seeded / self" in the role hierarchy — nothing in the API
creates one, since it's the only role with no creator above it. Run this
once per environment, after applying all Alembic migrations. Re-running the
command for the same email repairs a missing or inactive role assignment
without changing the existing account or password.

Usage: python -m scripts.seed_platform_admin --name "Jane Doe" --email jane@platform.io

The password is prompted without terminal echo so it is not exposed through
process arguments, command history, or process-inspection tools.
"""

import argparse
import asyncio
import getpass
import secrets
import uuid
from typing import Annotated

from pydantic import EmailStr, Field, TypeAdapter, ValidationError
from sqlalchemy import select

from app.common.security import hash_password, normalize_email, validate_password
from app.common.db.session import db_manager
from app.auth.models.platform_admin import PlatformAdmin
from app.auth.models.platform_role import PlatformRole
from app.auth.models.platform_user_role import PlatformUserRole
from app.auth.username_identity import username_base_from_email

_EMAIL_ADAPTER = TypeAdapter(Annotated[EmailStr, Field(max_length=254)])


def _prompt_for_password() -> str:
    password = getpass.getpass("Platform administrator password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if not secrets.compare_digest(password, confirmation):
        raise ValueError("Passwords do not match")
    return password


async def _seed(name: str, email: str, password: str | None = None) -> None:
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 255:
        raise ValueError("Name must contain between 1 and 255 non-whitespace characters")
    try:
        normalized_email = normalize_email(str(_EMAIL_ADAPTER.validate_python(email)))
    except ValidationError as exc:
        raise ValueError("A valid email address of at most 254 characters is required") from exc
    async with db_manager.session_for() as session:
        role = await session.scalar(
            select(PlatformRole).where(
                PlatformRole.role_code == "PLATFORM_ADMIN",
                PlatformRole.is_active.is_(True),
            )
        )
        if role is None:
            raise ValueError(
                "The active PLATFORM_ADMIN role does not exist; run "
                "'python -m alembic upgrade head' before this command"
            )

        existing = await session.scalar(
            select(PlatformAdmin).where(PlatformAdmin.email == normalized_email)
        )
        if existing is not None:
            assignment = await session.scalar(
                select(PlatformUserRole).where(
                    PlatformUserRole.admin_id == existing.admin_id,
                    PlatformUserRole.role_id == role.id,
                )
            )
            if assignment is None:
                session.add(
                    PlatformUserRole(
                        id=uuid.uuid4(),
                        admin_id=existing.admin_id,
                        role_id=role.id,
                        is_active=True,
                    )
                )
            elif not assignment.is_active:
                assignment.is_active = True
                assignment.revoked_at = None
                assignment.revoked_by = None
            else:
                print(
                    f"Platform admin {existing.admin_id} ({existing.email}) already has "
                    "the PLATFORM_ADMIN role; no changes made"
                )
                return

            await session.commit()
            print(
                f"Assigned PLATFORM_ADMIN role to existing platform admin "
                f"{existing.admin_id} ({existing.email})"
            )
            return

        if password is None:
            password = _prompt_for_password()
        validate_password(password, email=normalized_email, name=normalized_name)

        admin = PlatformAdmin(
            admin_id=uuid.uuid4(),
            name=normalized_name,
            email=normalized_email,
            username=username_base_from_email(normalized_email),
            password_hash=hash_password(password),
        )
        assignment = PlatformUserRole(
            id=uuid.uuid4(),
            admin_id=admin.admin_id,
            role_id=role.id,
            is_active=True,
        )
        session.add_all([admin, assignment])
        await session.commit()
        print(
            f"Created platform admin {admin.admin_id} ({admin.email}) and assigned "
            "the PLATFORM_ADMIN role"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the first platform administrator")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    try:
        asyncio.run(_seed(args.name, args.email))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
