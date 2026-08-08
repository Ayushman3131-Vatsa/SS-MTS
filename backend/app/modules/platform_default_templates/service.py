import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models.config_template import ConfigTemplate
from app.models.enums import PlatformActivityType, PlatformActorType
from app.models.platform_activity_event import PlatformActivityEvent
from app.modules.platform_default_templates import repository
from app.schemas.platform_default_template import (
    DefaultTemplateCreateRequest,
    DefaultTemplateDetailResponse,
    DefaultTemplateListItem,
    DefaultTemplatePlaceholder,
    DefaultTemplatePreviewRequest,
    DefaultTemplatePreviewResponse,
    DefaultTemplateUpdateRequest,
    PLACEHOLDER_TOKEN_RE,
    validate_template_content,
)


def _audit_snapshot(values: dict[str, object]) -> dict[str, object]:
    snapshot = dict(values)
    for field_name in ("template_id", "offering_id", "category_id"):
        value = snapshot.get(field_name)
        if isinstance(value, uuid.UUID):
            snapshot[field_name] = str(value)
    template_type = snapshot.get("type")
    if hasattr(template_type, "value"):
        snapshot["type"] = template_type.value
    return snapshot


def _read_model_snapshot(
    template: repository.DefaultTemplateReadModel,
) -> dict[str, object]:
    return _audit_snapshot(
        {
            "template_id": template.template_id,
            "offering_id": template.offering_id,
            "category_id": template.category_id,
            "code": template.code,
            "name": template.name,
            "description": template.description,
            "type": template.type,
            "subject": template.subject,
            "body": template.body,
            "placeholders": template.placeholders,
            "sort_order": template.sort_order,
            "is_active": template.is_active,
            "version": template.version,
        }
    )


def _record_activity(
    db: AsyncSession,
    *,
    principal: Principal,
    event_type: PlatformActivityType,
    template_id: uuid.UUID,
    old_value: dict[str, object] | None,
    new_value: dict[str, object],
    changed_fields: list[str],
) -> None:
    metadata: dict[str, object] = {
        "default_template": {
            "template_id": str(template_id),
            "offering_id": new_value["offering_id"],
            "category_id": new_value["category_id"],
            "code": new_value["code"],
            "name": new_value["name"],
            "type": new_value["type"],
            "version": new_value["version"],
        },
        "new_value": new_value,
        "changed_fields": changed_fields,
    }
    if old_value is not None:
        metadata["old_value"] = old_value
    db.add(
        PlatformActivityEvent(
            event_type=event_type.value,
            tenant_id=None,
            tenant_name_snapshot="Default template catalog",
            actor_id=principal.id,
            actor_type=PlatformActorType.PLATFORM_ADMIN.value,
            event_metadata=metadata,
            idempotency_key=(
                f"default-template:{event_type.value.lower()}:"
                f"{template_id}:{uuid.uuid4()}"
            ),
        )
    )


async def list_templates(
    db: AsyncSession,
    offering_id: uuid.UUID,
) -> list[DefaultTemplateListItem]:
    if await repository.get_offering(db, offering_id) is None:
        raise NotFoundError("Offering not found", code="OFFERING_NOT_FOUND")
    return [
        DefaultTemplateListItem.model_validate(item)
        for item in await repository.list_for_offering(db, offering_id)
    ]


async def get_template(
    db: AsyncSession,
    template_id: uuid.UUID,
) -> DefaultTemplateDetailResponse:
    template = await repository.get_detail(db, template_id)
    if template is None:
        raise NotFoundError(
            "Default template not found",
            code="DEFAULT_TEMPLATE_NOT_FOUND",
        )
    return DefaultTemplateDetailResponse.model_validate(template)


async def create_template(
    db: AsyncSession,
    principal: Principal,
    payload: DefaultTemplateCreateRequest,
) -> DefaultTemplateDetailResponse:
    offering = await repository.get_offering(db, payload.offering_id)
    if offering is None:
        raise NotFoundError("Offering not found", code="OFFERING_NOT_FOUND")

    try:
        category_id = await repository.get_or_create_typed_category(
            db,
            offering,
            payload.type.value,
        )
        template = ConfigTemplate(
            category_id=category_id,
            code=payload.code,
            display_name=payload.name,
            description=payload.description,
            template_type=payload.type.value,
            subject=payload.subject,
            body=payload.body,
            placeholders=[
                placeholder.model_dump() for placeholder in payload.placeholders
            ],
            sort_order=payload.sort_order,
            is_active=True,
            version=1,
        )
        db.add(template)
        await db.flush()
        new_value = _audit_snapshot(
            {
                "template_id": template.template_id,
                "offering_id": offering.offering_id,
                "category_id": category_id,
                "code": template.code,
                "name": template.display_name,
                "description": template.description,
                "type": template.template_type,
                "subject": template.subject,
                "body": template.body,
                "placeholders": template.placeholders,
                "sort_order": template.sort_order,
                "is_active": template.is_active,
                "version": template.version,
            }
        )
        _record_activity(
            db,
            principal=principal,
            event_type=PlatformActivityType.DEFAULT_TEMPLATE_CREATED,
            template_id=template.template_id,
            old_value=None,
            new_value=new_value,
            changed_fields=[
                "offering_id",
                "code",
                "name",
                "description",
                "type",
                "subject",
                "body",
                "placeholders",
                "sort_order",
                "is_active",
            ],
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(
            "A default template already uses this code",
            code="DEFAULT_TEMPLATE_CODE_EXISTS",
        ) from exc

    return await get_template(db, template.template_id)


async def update_template(
    db: AsyncSession,
    principal: Principal,
    template_id: uuid.UUID,
    payload: DefaultTemplateUpdateRequest,
) -> DefaultTemplateDetailResponse:
    current = await repository.get_detail(db, template_id)
    if current is None:
        raise NotFoundError(
            "Default template not found",
            code="DEFAULT_TEMPLATE_NOT_FOUND",
        )
    if current.version != payload.expected_version:
        raise ConflictError(
            "The default template changed after it was loaded",
            code="DEFAULT_TEMPLATE_STALE",
        )

    patch = payload.model_dump(exclude_unset=True, exclude={"expected_version"})
    merged_subject = patch.get("subject", current.subject)
    merged_body = patch.get("body", current.body)
    merged_placeholders = patch.get("placeholders", current.placeholders)
    if "placeholders" in patch:
        merged_placeholders = [
            placeholder.model_dump() for placeholder in payload.placeholders or []
        ]

    validated_placeholders = [
        DefaultTemplatePlaceholder.model_validate(placeholder)
        for placeholder in merged_placeholders
    ]
    current_placeholder_contract = {
        str(placeholder.get("key")): bool(placeholder.get("required", False))
        for placeholder in current.placeholders
        if isinstance(placeholder, dict)
    }
    updated_placeholder_contract = {
        placeholder.key: placeholder.required
        for placeholder in validated_placeholders
    }
    if updated_placeholder_contract != current_placeholder_contract:
        raise BusinessRuleError(
            "Placeholder keys and required flags cannot be changed after publishing",
            code="DEFAULT_TEMPLATE_PLACEHOLDER_CONTRACT_IMMUTABLE",
        )

    try:
        validate_template_content(
            merged_subject if isinstance(merged_subject, str) else None,
            str(merged_body),
            validated_placeholders,
        )
    except ValueError as exc:
        raise BusinessRuleError(
            str(exc),
            code="DEFAULT_TEMPLATE_PLACEHOLDERS_INVALID",
        ) from exc

    column_values: dict[str, object] = {}
    field_to_column = {
        "name": "display_name",
        "description": "description",
        "subject": "subject",
        "body": "body",
        "placeholders": "placeholders",
        "sort_order": "sort_order",
    }
    for field_name, value in patch.items():
        if field_name == "placeholders":
            value = merged_placeholders
        column_values[field_to_column[field_name]] = value

    updated = await repository.update_if_version(
        db,
        template_id,
        payload.expected_version,
        column_values,
    )
    if not updated:
        await db.rollback()
        raise ConflictError(
            "The default template changed after it was loaded",
            code="DEFAULT_TEMPLATE_STALE",
        )

    old_value = _read_model_snapshot(current)
    new_value = dict(old_value)
    new_value.update(
        {
            "name": patch.get("name", current.name),
            "description": patch.get("description", current.description),
            "subject": merged_subject,
            "body": merged_body,
            "placeholders": merged_placeholders,
            "sort_order": patch.get("sort_order", current.sort_order),
            "version": current.version + 1,
        }
    )
    current_values = {
        "name": current.name,
        "description": current.description,
        "subject": current.subject,
        "body": current.body,
        "placeholders": current.placeholders,
        "sort_order": current.sort_order,
    }
    candidate_values = {
        "name": patch.get("name", current.name),
        "description": patch.get("description", current.description),
        "subject": merged_subject,
        "body": merged_body,
        "placeholders": merged_placeholders,
        "sort_order": patch.get("sort_order", current.sort_order),
    }
    changed_fields = sorted(
        field_name
        for field_name in patch
        if candidate_values[field_name] != current_values[field_name]
    )
    _record_activity(
        db,
        principal=principal,
        event_type=PlatformActivityType.DEFAULT_TEMPLATE_UPDATED,
        template_id=template_id,
        old_value=old_value,
        new_value=_audit_snapshot(new_value),
        changed_fields=changed_fields,
    )
    await db.commit()
    return await get_template(db, template_id)


def preview_template(
    payload: DefaultTemplatePreviewRequest,
) -> DefaultTemplatePreviewResponse:
    context = {
        placeholder.key: payload.sample_data.get(
            placeholder.key,
            placeholder.sample_value,
        )
        for placeholder in payload.placeholders
    }

    def render(value: str) -> str:
        return PLACEHOLDER_TOKEN_RE.sub(
            lambda match: context[match.group(1)],
            value,
        )

    return DefaultTemplatePreviewResponse(
        subject=render(payload.subject) if payload.subject is not None else None,
        rendered_body=render(payload.body),
    )
