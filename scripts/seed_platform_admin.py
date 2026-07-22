"""Bootstrap the very first platform_admins row.

Administrator is "Seeded / self" in the role hierarchy — nothing in the API
creates one, since it's the only role with no creator above it. Run this
once per environment.

Usage: python -m scripts.seed_platform_admin --name "Jane Doe" --email jane@platform.io --password "..."
"""

import argparse
import asyncio

from app.core.security import hash_password
from app.db.session import db_manager
from app.models.platform_admin import PlatformAdmin


async def _seed(name: str, email: str, password: str) -> None:
    async with db_manager.session_for() as session:
        admin = PlatformAdmin(name=name, email=email, password_hash=hash_password(password))
        session.add(admin)
        await session.commit()
        print(f"Created platform admin {admin.admin_id} ({admin.email})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the first platform administrator")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    asyncio.run(_seed(args.name, args.email, args.password))


if __name__ == "__main__":
    main()
