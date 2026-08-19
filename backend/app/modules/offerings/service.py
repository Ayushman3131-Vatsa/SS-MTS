import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.enums import PlatformActivityType, PlatformActorType
from app.models.offering import Offering
from app.models.platform_activity_event import PlatformActivityEvent
from app.modules.offerings import repository
from app.schemas.offering import OfferingCreateRequest, OfferingDeleteRequest, OfferingUpdateRequest


def _snapshot(offering: Offering) -> dict[str, object]:
    return {
        "offering_id": str(offering.offering_id),
        "code": offering.code,
        "display_name": offering.display_name,
        "description": offering.description,
        "icon_key": offering.icon_key,
        "route_slug": offering.route_slug,
        "sort_order": offering.sort_order,
        "status": offering.status,
    }


async def _get_or_404(db: AsyncSession, offering_id: uuid.UUID) -> Offering:
    offering = await db.get(Offering, offering_id)
    if offering is None:
        raise NotFoundError("Offering not found", code="OFFERING_NOT_FOUND")
    return offering


def _record_activity(
    db: AsyncSession,
    *,
    principal: Principal,
    event_type: PlatformActivityType,
    offering: Offering,
    action: str,
    old_value: dict[str, object] | None,
    reason: str | None = None,
) -> None:
    metadata: dict[str, object] = {"offering": _snapshot(offering), "action": action}
    if old_value is not None:
        metadata["old_value"] = old_value
    if reason is not None:
        metadata["reason"] = reason
    db.add(
        PlatformActivityEvent(
            event_type=event_type.value,
            tenant_id=None,
            tenant_name_snapshot="Offering catalog",
            actor_id=principal.id,
            actor_type=PlatformActorType.PLATFORM_ADMIN.value,
            event_metadata=metadata,
            idempotency_key=f"offering-catalog:{action}:{offering.offering_id}:{uuid.uuid4()}",
        )
    )


async def list_catalog(db: AsyncSession) -> list[repository.OfferingCatalogReadModel]:
    return await repository.list_catalog(db)


async def create(
    db: AsyncSession, principal: Principal, payload: OfferingCreateRequest
) -> repository.OfferingCatalogReadModel:
    offering = Offering(**payload.model_dump())
    db.add(offering)
    try:
        await db.flush()
        _record_activity(
            db,
            principal=principal,
            event_type=PlatformActivityType.OFFERING_CATALOG_CREATED,
            offering=offering,
            action="CREATE",
            old_value=None,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("An offering already uses this code or route slug", code="OFFERING_DUPLICATE") from exc
    result = await repository.get_catalog_item(db, offering.offering_id)
    if result is None:
        raise RuntimeError("Offering could not be reloaded after creation")
    return result


async def update(
    db: AsyncSession,
    principal: Principal,
    offering_id: uuid.UUID,
    payload: OfferingUpdateRequest,
) -> repository.OfferingCatalogReadModel:
    offering = await _get_or_404(db, offering_id)
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise BusinessRuleError("Provide at least one field to update", code="OFFERING_UPDATE_EMPTY")
    old_value = _snapshot(offering)
    for field, value in values.items():
        setattr(offering, field, value)
    try:
        await db.flush()
        _record_activity(
            db,
            principal=principal,
            event_type=PlatformActivityType.OFFERING_CATALOG_UPDATED,
            offering=offering,
            action="UPDATE",
            old_value=old_value,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("An offering already uses this route slug", code="OFFERING_DUPLICATE") from exc
    result = await repository.get_catalog_item(db, offering_id)
    if result is None:
        raise RuntimeError("Offering could not be reloaded after update")
    return result


async def set_status(
    db: AsyncSession, principal: Principal, offering_id: uuid.UUID, status: str
) -> repository.OfferingCatalogReadModel:
    offering = await _get_or_404(db, offering_id)
    if offering.status == status:
        result = await repository.get_catalog_item(db, offering_id)
        if result is None:
            raise RuntimeError("Offering could not be reloaded")
        return result
    old_value = _snapshot(offering)
    offering.status = status
    event_type = (
        PlatformActivityType.OFFERING_CATALOG_ACTIVATED
        if status == "ACTIVE"
        else PlatformActivityType.OFFERING_CATALOG_DEACTIVATED
    )
    _record_activity(
        db,
        principal=principal,
        event_type=event_type,
        offering=offering,
        action="ACTIVATE" if status == "ACTIVE" else "DEACTIVATE",
        old_value=old_value,
    )
    await db.commit()
    result = await repository.get_catalog_item(db, offering_id)
    if result is None:
        raise RuntimeError("Offering could not be reloaded after status update")
    return result


async def remove(
    db: AsyncSession,
    principal: Principal,
    offering_id: uuid.UUID,
    payload: OfferingDeleteRequest,
) -> None:
    offering = await _get_or_404(db, offering_id)
    current = await repository.get_catalog_item(db, offering_id)
    if current is None:
        raise RuntimeError("Offering could not be inspected before deletion")
    if current.tenant_entitlement_count or current.configuration_category_count:
        raise BusinessRuleError(
            "This offering cannot be deleted because it has "
            f"{current.tenant_entitlement_count} tenant entitlement(s) and "
            f"{current.configuration_category_count} configuration category(s). Deactivate it instead.",
            code="OFFERING_IN_USE",
        )
    old_value = _snapshot(offering)
    _record_activity(
        db,
        principal=principal,
        event_type=PlatformActivityType.OFFERING_CATALOG_DELETED,
        offering=offering,
        action="DELETE",
        old_value=old_value,
        reason=payload.reason,
    )
    await db.delete(offering)
    await db.commit()
