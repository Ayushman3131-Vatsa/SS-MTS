"""Create the first Tenant Admin from a tenant's primary contact.

Usage:
    python -m scripts.bootstrap_tenant_admin --tenant-code ACME

This command uses the same onboarding service as the Platform Admin Enable
Tenant action. It prints the generated temporary password once after commit.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.auth.tenant_admin_onboarding import (
    enable_initial_tenant_admin,
    regenerate_initial_tenant_admin_password,
)
from app.common.db.session import db_manager
from app.tenant_management.models.tenant import Tenant


async def _bootstrap(tenant_code: str, *, rotate_pending: bool) -> tuple[str, str]:
    normalized_code = tenant_code.strip().upper()
    async with db_manager.session_for() as session:
        tenant = await session.scalar(
            select(Tenant).where(Tenant.tenant_code == normalized_code)
        )
        if tenant is None:
            raise ValueError(f"Tenant '{normalized_code}' was not found")
        try:
            result = (
                await regenerate_initial_tenant_admin_password(
                    session,
                    tenant_id=tenant.tenant_id,
                    platform_admin_id=None,
                    expected_version=tenant.version,
                    idempotency_key=f"cli-bootstrap-rotate:{tenant.tenant_id}:{tenant.version}",
                )
                if rotate_pending
                else await enable_initial_tenant_admin(
                    session,
                    tenant_id=tenant.tenant_id,
                    platform_admin_id=None,
                    expected_version=tenant.version,
                    idempotency_key=f"cli-bootstrap-enable:{tenant.tenant_id}:{tenant.version}",
                )
            )
        except Exception as exc:
            raise ValueError(str(exc)) from exc
        return result.email, result.temporary_password


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
