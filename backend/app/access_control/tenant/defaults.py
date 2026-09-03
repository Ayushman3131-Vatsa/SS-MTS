"""Default page grants for the existing seeded tenant system roles.

New role types are not invented here; custom roles stay empty until an admin
configures the matrix.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.catalog import (
    entitled_offering_codes,
    page_is_entitled,
    pages_for_realm,
)
from app.access_control.shared.enums import AccessLevel
from app.auth.models.page import Page
from app.auth.models.role import Role
from app.auth.models.role_page_access import RolePageAccess


def default_access_for_system_role(
    role_code: str,
    page: Page,
    *,
    entitled_codes: set[str],
) -> AccessLevel:
    if role_code == "TENANT_ADMIN" and page_is_entitled(page, entitled_codes):
        return "modify"
    return "none"


async def ensure_system_role_page_defaults(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    roles_result = await db.execute(
        select(Role).where(
            Role.tenant_id == tenant_id,
            Role.is_system.is_(True),
            Role.is_active.is_(True),
        )
    )
    roles = list(roles_result.scalars().all())
    if not roles:
        return

    pages = await pages_for_realm(db, "tenant")
    entitled_codes = await entitled_offering_codes(db, tenant_id)
    existing = await db.execute(
        select(RolePageAccess).where(RolePageAccess.role_id.in_([role.id for role in roles]))
    )
    existing_by_key = {
        (row.role_id, row.page_id): row for row in existing.scalars().all()
    }

    for role in roles:
        for page in pages:
            desired = default_access_for_system_role(
                role.role_code,
                page,
                entitled_codes=entitled_codes,
            )
            row = existing_by_key.get((role.id, page.id))
            if row is None:
                db.add(
                    RolePageAccess(
                        role_id=role.id,
                        page_id=page.id,
                        access_level=desired,
                    )
                )
            elif row.access_level != desired:
                row.access_level = desired
    await db.flush()
