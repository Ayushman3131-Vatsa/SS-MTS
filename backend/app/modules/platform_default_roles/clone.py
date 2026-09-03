"""Clone platform default-role templates into a tenant workspace."""

from __future__ import annotations

from dataclasses import dataclass
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.catalog import CORE_MODULE_SCOPE, tenant_pages_for_entitlements
from app.auth.models.platform_default_role import PlatformDefaultRole
from app.auth.models.platform_default_role_page_access import PlatformDefaultRolePageAccess
from app.auth.models.role import Role
from app.auth.models.role_page_access import RolePageAccess
from app.common.exceptions import BusinessRuleError, NotFoundError


@dataclass(frozen=True)
class TemplateChoice:
    role_id: uuid.UUID
    role_code: str
    role_name: str
    offering_id: uuid.UUID | None
    module_scope: str
    is_system: bool
    modify_count: int


def pick_bootstrap_templates(templates: list[TemplateChoice]) -> list[TemplateChoice]:
    """One admin-style template per module: TENANT_ADMIN, then *ADMIN*, then most modify grants."""
    by_scope: dict[str, list[TemplateChoice]] = {}
    for template in templates:
        by_scope.setdefault(template.module_scope, []).append(template)
    chosen: list[TemplateChoice] = []
    for scope in sorted(by_scope, key=lambda value: (value != CORE_MODULE_SCOPE, value)):
        roles = by_scope[scope]
        exact_admin = next((role for role in roles if role.role_code == "TENANT_ADMIN"), None)
        named_admin = next(
            (role for role in roles if "ADMIN" in role.role_code or "MANAGER" in role.role_code),
            None,
        )
        richest = max(roles, key=lambda role: (role.modify_count, role.is_system, role.role_name))
        chosen.append(exact_admin or named_admin or richest)
    return chosen


async def list_active_templates_for_offerings(
    db: AsyncSession,
    offering_ids: set[uuid.UUID],
) -> list[PlatformDefaultRole]:
    query = select(PlatformDefaultRole).where(PlatformDefaultRole.is_active.is_(True))
    if offering_ids:
        query = query.where(
            (PlatformDefaultRole.offering_id.is_(None))
            | (PlatformDefaultRole.offering_id.in_(offering_ids))
        )
    else:
        query = query.where(PlatformDefaultRole.offering_id.is_(None))
    result = await db.execute(query.order_by(PlatformDefaultRole.module_scope, PlatformDefaultRole.role_name))
    return list(result.scalars().all())


async def clone_default_roles_for_tenant(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    offering_ids: set[uuid.UUID],
) -> dict[uuid.UUID, Role]:
    """Create tenant roles from active templates. Returns template id → tenant Role."""
    templates = await list_active_templates_for_offerings(db, offering_ids)
    if not templates:
        return {}

    existing_result = await db.execute(select(Role).where(Role.tenant_id == tenant_id))
    existing_by_code = {role.role_code: role for role in existing_result.scalars().all()}
    entitled_pages = await tenant_pages_for_entitlements(db, tenant_id)
    entitled_ids = {page.id for page in entitled_pages}
    cloned: dict[uuid.UUID, Role] = {}

    for template in templates:
        role = existing_by_code.get(template.role_code)
        if role is None:
            role = Role(
                tenant_id=tenant_id,
                role_code=template.role_code,
                role_name=template.role_name,
                description=template.description,
                is_system=template.is_system,
                is_active=True,
                module_scope=template.module_scope,
            )
            db.add(role)
            await db.flush()
            existing_by_code[role.role_code] = role
        elif role.module_scope is None:
            role.module_scope = template.module_scope

        access_rows = await db.execute(
            select(PlatformDefaultRolePageAccess).where(
                PlatformDefaultRolePageAccess.role_id == template.id
            )
        )
        existing_access = await db.execute(
            select(RolePageAccess.page_id).where(RolePageAccess.role_id == role.id)
        )
        present = set(existing_access.scalars().all())
        for grant in access_rows.scalars().all():
            if grant.page_id not in entitled_ids or grant.page_id in present:
                continue
            db.add(
                RolePageAccess(
                    role_id=role.id,
                    page_id=grant.page_id,
                    access_level=grant.access_level,
                )
            )
            present.add(grant.page_id)
        cloned[template.id] = role

    await db.flush()
    return cloned


async def resolve_bootstrap_roles(
    db: AsyncSession,
    *,
    cloned: dict[uuid.UUID, Role],
    requested_template_ids: list[uuid.UUID],
    templates: list[PlatformDefaultRole],
) -> list[Role]:
    if requested_template_ids:
        unique_ids = list(dict.fromkeys(requested_template_ids))
        missing = [role_id for role_id in unique_ids if role_id not in cloned]
        if missing:
            raise NotFoundError(
                "One or more default roles are not available for the selected modules",
                code="BOOTSTRAP_ROLE_NOT_FOUND",
            )
        return [cloned[role_id] for role_id in unique_ids]

    choices = []
    for template in templates:
        modify_count = 0
        grants = await db.execute(
            select(PlatformDefaultRolePageAccess.access_level).where(
                PlatformDefaultRolePageAccess.role_id == template.id
            )
        )
        modify_count = sum(1 for level in grants.scalars().all() if level == "modify")
        choices.append(
            TemplateChoice(
                role_id=template.id,
                role_code=template.role_code,
                role_name=template.role_name,
                offering_id=template.offering_id,
                module_scope=template.module_scope,
                is_system=template.is_system,
                modify_count=modify_count,
            )
        )
    picked = pick_bootstrap_templates(choices)
    if not picked:
        raise BusinessRuleError(
            "No default roles are configured to assign on registration",
            code="BOOTSTRAP_ROLE_UNAVAILABLE",
        )
    return [cloned[choice.role_id] for choice in picked if choice.role_id in cloned]


def is_module_admin_role_code(role_code: str) -> bool:
    return role_code.upper().endswith("_ADMIN")


def resolve_registration_admin_roles(
    *,
    cloned: dict[uuid.UUID, Role],
    templates: list[PlatformDefaultRole],
    offerings: list,
    seeded_tenant_admin: Role | None,
) -> list[Role]:
    """Assign every cloned *_ADMIN role. Fail if a purchased module has none."""
    chosen: list[Role] = []
    seen: set[uuid.UUID] = set()

    def add(role: Role | None) -> None:
        if role is None or role.id in seen:
            return
        seen.add(role.id)
        chosen.append(role)

    tenant_admin = next((role for role in cloned.values() if role.role_code == "TENANT_ADMIN"), None)
    add(tenant_admin or seeded_tenant_admin)
    if not any(role.role_code == "TENANT_ADMIN" for role in chosen):
        raise BusinessRuleError(
            "Workspace administrator role TENANT_ADMIN is not configured",
            code="MODULE_ADMIN_ROLE_MISSING",
        )

    templates_by_id = {template.id: template for template in templates}
    for offering in offerings:
        offering_admins = [
            cloned[template.id]
            for template in templates
            if (
                template.offering_id == offering.offering_id
                or (
                    offering.code in {"TENANT_ADMINISTRATION", "USER_ACCESS_MANAGEMENT"}
                    and (
                        template.role_code == "TENANT_ADMIN"
                        or (template.module_scope and template.module_scope.lower() in {"tenant_administration", "user_access_management", "core"})
                    )
                )
            )
            and is_module_admin_role_code(template.role_code)
            and template.id in cloned
        ]
        if not offering_admins and offering.code in {"TENANT_ADMINISTRATION", "USER_ACCESS_MANAGEMENT"}:
            if tenant_admin:
                offering_admins = [tenant_admin]
            elif seeded_tenant_admin:
                offering_admins = [seeded_tenant_admin]

        if not offering_admins:
            raise BusinessRuleError(
                f"No administrator role (_ADMIN) is configured for {offering.display_name}",
                code="MODULE_ADMIN_ROLE_MISSING",
            )
        for role in offering_admins:
            add(role)

    for template_id, role in cloned.items():
        template = templates_by_id.get(template_id)
        if template is not None and is_module_admin_role_code(template.role_code):
            add(role)
        elif is_module_admin_role_code(role.role_code):
            add(role)
    return chosen

