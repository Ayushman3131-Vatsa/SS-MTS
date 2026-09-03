from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.access_control.shared.catalog import (
    CORE_MODULE_SCOPE,
    CORE_TENANT_PAGE_CODES,
    page_access_response,
    page_response,
    pages_for_realm,
    role_code,
)
from app.auth.models.page import Page
from app.auth.models.platform_default_role import PlatformDefaultRole
from app.auth.models.platform_default_role_page_access import PlatformDefaultRolePageAccess
from app.common.deps import Principal
from app.common.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.modules.platform_default_roles import repository
from app.modules.platform_default_roles.schemas import (
    DefaultRoleCreateRequest,
    DefaultRoleDetailResponse,
    DefaultRoleListItem,
    DefaultRolePageAccessUpdate,
    DefaultRolePagesResponse,
    DefaultRoleUpdateRequest,
)
from app.tenant_management.models.enums import PlatformActivityType, PlatformActorType
from app.tenant_management.models.offering import Offering
from app.tenant_management.models.platform_activity_event import PlatformActivityEvent


def _audit_snapshot(role: repository.DefaultRoleReadModel) -> dict[str, object]:
    return {
        "role_id": str(role.role_id),
        "role_code": role.role_code,
        "role_name": role.role_name,
        "description": role.description,
        "offering_id": str(role.offering_id) if role.offering_id else None,
        "module_scope": role.module_scope,
        "is_system": role.is_system,
        "is_active": role.is_active,
        "version": role.version,
    }


def _record_activity(
    db: AsyncSession,
    *,
    principal: Principal,
    event_type: PlatformActivityType,
    role_id: uuid.UUID,
    new_value: dict[str, object],
    old_value: dict[str, object] | None = None,
) -> None:
    metadata: dict[str, object] = {
        "default_role": {
            "role_id": str(role_id),
            "role_code": new_value["role_code"],
            "role_name": new_value["role_name"],
            "module_scope": new_value["module_scope"],
        },
        "new_value": new_value,
    }
    if old_value is not None:
        metadata["old_value"] = old_value
    db.add(
        PlatformActivityEvent(
            event_type=event_type.value,
            tenant_id=None,
            tenant_name_snapshot="Default role catalog",
            actor_id=principal.id,
            actor_type=PlatformActorType.PLATFORM_ADMIN.value,
            event_metadata=metadata,
            idempotency_key=f"default-role:{event_type.value.lower()}:{role_id}:{uuid.uuid4()}",
        )
    )


def _to_list_item(role: repository.DefaultRoleReadModel) -> DefaultRoleListItem:
    return DefaultRoleListItem.model_validate(role, from_attributes=True)


async def _pages_for_scope(
    db: AsyncSession,
    *,
    offering: Offering | None,
    module_scope: str | None = None,
) -> list[Page]:
    pages = await pages_for_realm(db, "tenant")
    if offering is None:
        if module_scope == "user_access_management":
            return [page for page in pages if page.module == "user_access_management"]
        if module_scope == "tenant_administration":
            return [page for page in pages if page.module == "tenant_administration"]
        return [page for page in pages if page.page_code in CORE_TENANT_PAGE_CODES]
    return [page for page in pages if page.offering_code == offering.code]


async def _resolve_scope(
    db: AsyncSession,
    offering_id: uuid.UUID | None,
    module_scope: str | None = None,
) -> tuple[Offering | None, str]:
    if offering_id is None:
        if module_scope:
            matched = await repository.get_offering_by_code_or_slug(db, module_scope)
            if matched:
                return matched, matched.code
        return None, CORE_MODULE_SCOPE
    offering = await repository.get_offering(db, offering_id)
    if offering is None:
        raise NotFoundError("Offering not found", code="OFFERING_NOT_FOUND")
    return offering, offering.code


async def _build_detail(
    db: AsyncSession, role: repository.DefaultRoleReadModel
) -> DefaultRoleDetailResponse:
    offering = await repository.get_offering(db, role.offering_id) if role.offering_id else None
    pages = await _pages_for_scope(db, offering=offering, module_scope=role.module_scope)
    access_rows = await repository.list_access_by_role(db, role.role_id)
    by_page_id = {row.page_id: row.access_level for row in access_rows}
    page_access = [page_access_response(page, by_page_id.get(page.id, "none")) for page in pages]
    return DefaultRoleDetailResponse(
        **_to_list_item(role).model_dump(),
        page_access=page_access,
    )


async def list_roles(
    db: AsyncSession,
    *,
    offering_id: uuid.UUID | None = None,
    core_only: bool = False,
) -> list[DefaultRoleListItem]:
    if offering_id is not None:
        await _resolve_scope(db, offering_id)
    roles = await repository.list_roles(db, offering_id=offering_id, core_only=core_only)
    return [_to_list_item(role) for role in roles]


async def get_role(db: AsyncSession, role_id: uuid.UUID) -> DefaultRoleDetailResponse:
    role = await repository.get_role(db, role_id)
    if role is None:
        raise NotFoundError("Default role not found", code="DEFAULT_ROLE_NOT_FOUND")
    return await _build_detail(db, role)


async def list_scope_pages(
    db: AsyncSession, *, offering_id: uuid.UUID | None
) -> DefaultRolePagesResponse:
    offering, module_scope = await _resolve_scope(db, offering_id)
    pages = await _pages_for_scope(db, offering=offering, module_scope=module_scope)
    return DefaultRolePagesResponse(
        module_scope=module_scope,
        offering_id=offering.offering_id if offering else None,
        offering_code=offering.code if offering else None,
        offering_name=offering.display_name if offering else None,
        pages=[page_response(page) for page in pages],
    )


async def _upsert_access(
    db: AsyncSession,
    *,
    role_id: uuid.UUID,
    page_id: uuid.UUID,
    access_level: str,
    actor_id: uuid.UUID,
) -> None:
    existing = await db.execute(
        select(PlatformDefaultRolePageAccess).where(
            PlatformDefaultRolePageAccess.role_id == role_id,
            PlatformDefaultRolePageAccess.page_id == page_id,
        )
    )
    row = existing.scalar_one_or_none()
    if row is None:
        db.add(
            PlatformDefaultRolePageAccess(
                role_id=role_id,
                page_id=page_id,
                access_level=access_level,
                updated_by=actor_id,
            )
        )
        return
    await db.execute(
        update(PlatformDefaultRolePageAccess)
        .where(PlatformDefaultRolePageAccess.id == row.id)
        .values(access_level=access_level, updated_by=actor_id)
    )


async def _apply_entries(
    db: AsyncSession,
    *,
    role_id: uuid.UUID,
    pages: list[Page],
    entries: list[DefaultRolePageAccessUpdate],
    actor_id: uuid.UUID,
) -> None:
    valid_page_ids = {page.id for page in pages}
    for entry in entries:
        if entry.page_id not in valid_page_ids:
            raise BusinessRuleError(
                "One or more pages do not belong to this module",
                code="PAGE_OUT_OF_SCOPE",
            )
        await _upsert_access(
            db,
            role_id=role_id,
            page_id=entry.page_id,
            access_level=entry.access_level,
            actor_id=actor_id,
        )


async def create_role(
    db: AsyncSession,
    principal: Principal,
    payload: DefaultRoleCreateRequest,
) -> DefaultRoleDetailResponse:
    offering, default_scope = await _resolve_scope(
        db, payload.offering_id, payload.module_scope
    )
    module_scope = payload.module_scope or default_scope
    offering_id = payload.offering_id or (offering.offering_id if offering else None)
    pages = await _pages_for_scope(db, offering=offering, module_scope=module_scope)
    code = payload.role_code or role_code(payload.role_name)
    role = PlatformDefaultRole(
        offering_id=offering_id,
        role_code=code,
        role_name=payload.role_name,
        description=payload.description,
        module_scope=module_scope,
        is_system=payload.is_system,
        is_active=payload.is_active,
        version=1,
    )
    db.add(role)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("A default role with this code already exists for the module") from exc

    access_by_page = {entry.page_id: entry.access_level for entry in payload.entries}
    for page in pages:
        db.add(
            PlatformDefaultRolePageAccess(
                role_id=role.id,
                page_id=page.id,
                access_level=access_by_page.get(page.id, "none"),
                updated_by=principal.id,
            )
        )
    created = await repository.get_role(db, role.id)
    if created is None:
        raise RuntimeError("Created default role could not be reloaded")
    _record_activity(
        db,
        principal=principal,
        event_type=PlatformActivityType.DEFAULT_ROLE_CREATED,
        role_id=role.id,
        new_value=_audit_snapshot(created),
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("A default role with this code already exists for the module") from exc
    return await get_role(db, role.id)


async def update_role(
    db: AsyncSession,
    principal: Principal,
    role_id: uuid.UUID,
    payload: DefaultRoleUpdateRequest,
) -> DefaultRoleDetailResponse:
    current = await repository.get_role(db, role_id)
    model = await repository.get_role_model(db, role_id)
    if current is None or model is None:
        raise NotFoundError("Default role not found", code="DEFAULT_ROLE_NOT_FOUND")
    if model.version != payload.version:
        raise ConflictError("Default role was modified by someone else — refresh and retry")

    offering = await repository.get_offering(db, model.offering_id) if model.offering_id else None
    pages = await _pages_for_scope(db, offering=offering)
    if payload.role_name is not None:
        model.role_name = payload.role_name
    if payload.description is not None:
        model.description = payload.description
    if payload.is_active is not None:
        model.is_active = payload.is_active
    if payload.entries is not None:
        await _apply_entries(
            db,
            role_id=role_id,
            pages=pages,
            entries=payload.entries,
            actor_id=principal.id,
        )
    model.version += 1
    await db.flush()
    updated = await repository.get_role(db, role_id)
    if updated is None:
        raise RuntimeError("Updated default role could not be reloaded")
    _record_activity(
        db,
        principal=principal,
        event_type=PlatformActivityType.DEFAULT_ROLE_UPDATED,
        role_id=role_id,
        old_value=_audit_snapshot(current),
        new_value=_audit_snapshot(updated),
    )
    await db.commit()
    return await get_role(db, role_id)


async def delete_role(
    db: AsyncSession,
    principal: Principal,
    role_id: uuid.UUID,
) -> None:
    current = await repository.get_role(db, role_id)
    model = await repository.get_role_model(db, role_id)
    if current is None or model is None:
        raise NotFoundError("Default role not found", code="DEFAULT_ROLE_NOT_FOUND")
    if model.is_system:
        raise BusinessRuleError("System default roles cannot be deleted", code="SYSTEM_ROLE_LOCKED")
    _record_activity(
        db,
        principal=principal,
        event_type=PlatformActivityType.DEFAULT_ROLE_DELETED,
        role_id=role_id,
        new_value=_audit_snapshot(current),
        old_value=_audit_snapshot(current),
    )
    await db.delete(model)
    await db.commit()
