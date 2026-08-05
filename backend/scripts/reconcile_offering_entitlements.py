"""Mark expired offering entitlements and write their durable audit trail.

Run this command from a scheduler (for example, every minute). Access checks
still use database time on every request, so a delayed run cannot extend access.
"""

import asyncio

from app.db.session import db_manager
from app.modules.tenants.service import (
    purge_retired_offerings,
    reconcile_expired_offerings,
)


async def _reconcile() -> None:
    async with db_manager.session_for() as session:
        expired = await reconcile_expired_offerings(session)
        purged = await purge_retired_offerings(session)
    print(
        "Offering entitlement reconciliation complete: "
        f"{expired} expired, {purged} retention-purged entitlement(s)."
    )


def main() -> None:
    asyncio.run(_reconcile())


if __name__ == "__main__":
    main()
