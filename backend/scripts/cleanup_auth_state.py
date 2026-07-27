"""Remove expired browser sessions and stale authentication throttle rows.

Schedule this command periodically (for example, every 15 minutes):

    python -m scripts.cleanup_auth_state
"""

import asyncio

from app.db.session import db_manager
from app.modules.auth.service import cleanup_expired_auth_state


async def _cleanup() -> None:
    async with db_manager.session_for() as session:
        result = await cleanup_expired_auth_state(session)
    print(
        "Authentication cleanup complete: "
        f"{result.sessions_deleted} session(s), "
        f"{result.throttle_rows_deleted} throttle row(s) removed."
    )


def main() -> None:
    asyncio.run(_cleanup())


if __name__ == "__main__":
    main()
