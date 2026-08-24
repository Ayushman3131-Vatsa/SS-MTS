"""Canonical system role codes / display names used across authz."""

from __future__ import annotations

# role_code → role_name (role_name is what Principal.role / authz expect)
SYSTEM_ROLES: tuple[tuple[str, str], ...] = (
    ("TENANT_ADMIN", "Tenant Admin"),
)

ROLE_CODE_BY_NAME: dict[str, str] = {name: code for code, name in SYSTEM_ROLES}
ROLE_NAME_BY_CODE: dict[str, str] = {code: name for code, name in SYSTEM_ROLES}
