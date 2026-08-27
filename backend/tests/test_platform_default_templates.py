from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
import uuid

import pytest
from fastapi import Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.deps import Principal, require_platform_admin
from app.core.exceptions import BusinessRuleError, ConflictError, ForbiddenError
from app.main import app as production_app
from app.models.config_category import ConfigCategory
from app.models.config_template import ConfigTemplate
from app.models.enums import PlatformActivityType
from app.models.offering import Offering
from app.models.platform_activity_event import PlatformActivityEvent
from app.models.tenant import Tenant
from app.models.tenant_config_override import TenantConfigOverride
from app.models.tenant_offering import TenantOffering
from app.auth.models.user_account import UserAccount
from app.modules.configurations import service as tenant_configuration_service
from app.modules.platform_default_templates import repository, service
from app.modules.platform_default_templates import router as platform_template_router
from app.schemas.platform_default_template import (
    DefaultTemplateCreateRequest,
    DefaultTemplatePreviewRequest,
    DefaultTemplateUpdateRequest,
)


NOW = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
ADMIN = Principal(
    type="admin",
    id=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
    email="operator@example.test",
)


def _placeholder(
    key: str = "employee_name",
    *,
    label: str = "Employee name",
    required: bool = True,
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "sample_value": "Ada Lovelace",
        "required": required,
    }


def _read_model(**overrides) -> repository.DefaultTemplateReadModel:
    values = {
        "template_id": uuid.UUID("11111111-1111-4111-8111-111111111111"),
        "offering_id": uuid.UUID("22222222-2222-4222-8222-222222222222"),
        "offering_code": "CORE_HR",
        "offering_name": "Core HR",
        "category_id": uuid.UUID("33333333-3333-4333-8333-333333333333"),
        "category_code": "corehr_email_templates",
        "category_name": "Email Templates",
        "code": "welcome_email",
        "name": "Welcome email",
        "description": "Welcomes a new employee",
        "type": "EMAIL",
        "subject": "Welcome {{employee_name}}",
        "body": "Hello {{employee_name}}",
        "placeholders": [_placeholder()],
        "sort_order": 10,
        "is_active": True,
        "version": 1,
        "created_at": NOW,
        "updated_at": NOW,
        "inheriting_tenant_count": 3,
        "customized_tenant_count": 2,
    }
    values.update(overrides)
    return repository.DefaultTemplateReadModel(**values)


class _Session:
    def __init__(self) -> None:
        self.add = Mock()
        self.commit = AsyncMock()
        self.rollback = AsyncMock()


def test_create_contract_normalizes_identity_and_allows_unused_optional_placeholder() -> None:
    payload = DefaultTemplateCreateRequest(
        offering_id=uuid.uuid4(),
        code=" WELCOME_EMAIL ",
        name=" Welcome email ",
        description=" First-day message ",
        type="EMAIL",
        subject="Welcome {{employee_name}}",
        body="Hello {{employee_name}}",
        placeholders=[
            _placeholder(),
            _placeholder("manager_name", label="Manager", required=False),
        ],
        sort_order=10,
    )

    assert payload.code == "welcome_email"
    assert payload.name == "Welcome email"
    assert payload.description == "First-day message"
    assert payload.placeholders[1].key == "manager_name"


@pytest.mark.parametrize(
    "overrides",
    [
        {"code": 123},
        {"placeholders": [{**_placeholder(), "key": 123}]},
        {"placeholders": [{**_placeholder(), "label": 123}]},
    ],
)
def test_create_contract_reports_wrong_text_types_as_validation_errors(
    overrides: dict[str, object],
) -> None:
    values: dict[str, object] = {
        "offering_id": uuid.uuid4(),
        "code": "welcome_email",
        "name": "Welcome email",
        "type": "EMAIL",
        "body": "Hello {{employee_name}}",
        "placeholders": [_placeholder()],
    }
    values.update(overrides)

    with pytest.raises(ValidationError):
        DefaultTemplateCreateRequest.model_validate(values)


@pytest.mark.parametrize(
    ("body", "placeholders", "message"),
    [
        ("Hello {{unknown}}", [], "undeclared placeholders"),
        ("Hello {{ employee_name }}", [_placeholder()], "malformed placeholder"),
        ("Hello {{{employee_name}}}", [_placeholder()], "malformed placeholder"),
        ("Hello", [_placeholder()], "missing required placeholders"),
        (
            "Hello {{employee_name}}",
            [_placeholder(), _placeholder()],
            "placeholder keys must be unique",
        ),
    ],
)
def test_create_contract_rejects_invalid_placeholder_content(
    body: str,
    placeholders: list[dict[str, object]],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        DefaultTemplateCreateRequest(
            offering_id=uuid.uuid4(),
            code="welcome_email",
            name="Welcome email",
            type="EMAIL",
            body=body,
            placeholders=placeholders,
        )


def test_patch_contract_exposes_only_safe_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DefaultTemplateUpdateRequest(
            expected_version=1,
            code="renamed_code",  # type: ignore[call-arg]
        )
    with pytest.raises(ValidationError, match="provide at least one"):
        DefaultTemplateUpdateRequest(expected_version=1)


def test_preview_uses_request_samples_then_placeholder_defaults() -> None:
    payload = DefaultTemplatePreviewRequest(
        subject="Welcome {{employee_name}}",
        body="Manager: {{manager_name}}",
        placeholders=[
            _placeholder(),
            {
                **_placeholder("manager_name", label="Manager", required=True),
                "sample_value": "Grace Hopper",
            },
        ],
        sample_data={"employee_name": "Katherine Johnson"},
    )

    result = service.preview_template(payload)

    assert result.subject == "Welcome Katherine Johnson"
    assert result.rendered_body == "Manager: Grace Hopper"


@pytest.mark.asyncio
async def test_platform_template_route_sets_private_no_store() -> None:
    response = Response()
    payload = DefaultTemplatePreviewRequest(
        body="Hello {{employee_name}}",
        placeholders=[_placeholder()],
    )

    await platform_template_router.preview_default_template(
        payload,
        response,
        ADMIN,
    )

    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_tenant_principal_is_forbidden_from_platform_templates() -> None:
    tenant_principal = Principal(
        type="user",
        id=uuid.uuid4(),
        email="tenant@example.test",
        tenant_id=uuid.uuid4(),
        role="Tenant Admin",
        tenant_status="ACTIVE",
    )

    with pytest.raises(ForbiddenError):
        await require_platform_admin(tenant_principal)


@pytest.mark.asyncio
async def test_update_rejects_stale_version_before_mutation() -> None:
    db = _Session()
    with (
        patch.object(
            repository,
            "get_detail",
            new=AsyncMock(return_value=_read_model(version=2)),
        ),
        patch.object(
            repository,
            "update_if_version",
            new=AsyncMock(),
        ) as update_if_version,
    ):
        with pytest.raises(ConflictError) as captured:
            await service.update_template(
                db,  # type: ignore[arg-type]
                ADMIN,
                _read_model().template_id,
                DefaultTemplateUpdateRequest(
                    expected_version=1,
                    name="New name",
                ),
            )

    assert captured.value.code == "DEFAULT_TEMPLATE_STALE"
    update_if_version.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "placeholders",
    [
        [_placeholder("renamed_key")],
        [_placeholder(required=False)],
    ],
)
async def test_update_keeps_published_placeholder_contract_immutable(
    placeholders: list[dict[str, object]],
) -> None:
    db = _Session()
    with patch.object(
        repository,
        "get_detail",
        new=AsyncMock(return_value=_read_model()),
    ):
        with pytest.raises(BusinessRuleError) as captured:
            await service.update_template(
                db,  # type: ignore[arg-type]
                ADMIN,
                _read_model().template_id,
                DefaultTemplateUpdateRequest(
                    expected_version=1,
                    placeholders=placeholders,
                ),
            )

    assert (
        captured.value.code
        == "DEFAULT_TEMPLATE_PLACEHOLDER_CONTRACT_IMMUTABLE"
    )


@pytest.mark.asyncio
async def test_concurrent_update_failure_returns_stale_conflict() -> None:
    db = _Session()
    current = _read_model()
    with (
        patch.object(
            repository,
            "get_detail",
            new=AsyncMock(return_value=current),
        ),
        patch.object(
            repository,
            "update_if_version",
            new=AsyncMock(return_value=False),
        ),
    ):
        with pytest.raises(ConflictError) as captured:
            await service.update_template(
                db,  # type: ignore[arg-type]
                ADMIN,
                current.template_id,
                DefaultTemplateUpdateRequest(
                    expected_version=1,
                    name="Concurrent name",
                ),
            )

    assert captured.value.code == "DEFAULT_TEMPLATE_STALE"
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_records_safe_changed_fields_and_increments_version() -> None:
    db = _Session()
    current = _read_model()
    changed_placeholders = [
        _placeholder(label="Employee legal name"),
    ]
    updated = replace(
        current,
        name="Updated welcome email",
        placeholders=changed_placeholders,
        version=2,
    )
    with (
        patch.object(
            repository,
            "get_detail",
            new=AsyncMock(side_effect=[current, updated]),
        ),
        patch.object(
            repository,
            "update_if_version",
            new=AsyncMock(return_value=True),
        ) as update_if_version,
    ):
        result = await service.update_template(
            db,  # type: ignore[arg-type]
            ADMIN,
            current.template_id,
            DefaultTemplateUpdateRequest(
                expected_version=1,
                name="Updated welcome email",
                placeholders=changed_placeholders,
            ),
        )

    assert result.version == 2
    update_if_version.assert_awaited_once()
    assert update_if_version.await_args.args[2] == 1
    activity = db.add.call_args.args[0]
    assert activity.event_type == PlatformActivityType.DEFAULT_TEMPLATE_UPDATED.value
    assert activity.event_metadata["changed_fields"] == ["name", "placeholders"]
    assert "expected_version" not in activity.event_metadata["changed_fields"]
    db.commit.assert_awaited_once()


def test_openapi_registers_platform_only_crud_without_delete_or_deactivate() -> None:
    schema = production_app.openapi()
    base = schema["paths"]["/platform/default-templates"]
    detail = schema["paths"]["/platform/default-templates/{template_id}"]
    preview = schema["paths"]["/platform/default-templates/preview"]

    assert set(base) == {"get", "post"}
    assert set(detail) == {"get", "patch"}
    assert set(preview) == {"post"}
    offering_parameter = next(
        parameter
        for parameter in base["get"]["parameters"]
        if parameter["name"] == "offering_id"
    )
    assert offering_parameter["required"] is True
    assert base["get"]["security"] == [
        {"BearerAuth": []},
        {"BrowserSession": []},
    ]


@pytest.mark.asyncio
async def test_create_publishes_active_and_reuses_typed_category(
    db_session: AsyncSession,
) -> None:
    suffix = uuid.uuid4().hex[:10]
    offering = Offering(
        code=f"TPL_{suffix.upper()}",
        display_name="Template Test Offering",
        description="Exercises platform template publishing",
        icon_key="file-text",
        route_slug=f"template-test-{suffix}",
        sort_order=999,
        status="ACTIVE",
    )
    db_session.add(offering)
    await db_session.flush()

    def payload(code: str, name: str) -> DefaultTemplateCreateRequest:
        return DefaultTemplateCreateRequest(
            offering_id=offering.offering_id,
            code=code,
            name=name,
            description="Published default",
            type="EMAIL",
            subject="Welcome {{employee_name}}",
            body="Hello {{employee_name}}",
            placeholders=[_placeholder()],
            sort_order=10,
        )

    first = await service.create_template(
        db_session,
        ADMIN,
        payload(f"welcome_{suffix}", "Welcome"),
    )
    second = await service.create_template(
        db_session,
        ADMIN,
        payload(f"reminder_{suffix}", "Reminder"),
    )

    assert first.is_active is True
    assert first.version == 1
    assert first.category_id == second.category_id
    assert first.category_name == "Email Templates"
    assert first.inheriting_tenant_count == 0
    assert first.customized_tenant_count == 0
    category = await db_session.get(ConfigCategory, first.category_id)
    assert category is not None
    assert category.template_type == "EMAIL"
    events = (
        await db_session.execute(
            select(PlatformActivityEvent).where(
                PlatformActivityEvent.event_type
                == PlatformActivityType.DEFAULT_TEMPLATE_CREATED.value,
                PlatformActivityEvent.actor_id == ADMIN.id,
            )
        )
    ).scalars().all()
    assert len(events) >= 2


@pytest.mark.asyncio
async def test_global_code_conflict_spans_offerings_and_template_types(
    db_session: AsyncSession,
) -> None:
    suffix = uuid.uuid4().hex[:10]
    offerings = [
        Offering(
            code=f"DUPA_{suffix.upper()}",
            display_name="Duplicate A",
            description="First offering",
            icon_key="mail",
            route_slug=f"duplicate-a-{suffix}",
            sort_order=1000,
            status="ACTIVE",
        ),
        Offering(
            code=f"DUPB_{suffix.upper()}",
            display_name="Duplicate B",
            description="Second offering",
            icon_key="file-text",
            route_slug=f"duplicate-b-{suffix}",
            sort_order=1001,
            status="ACTIVE",
        ),
    ]
    connection = await db_session.connection()
    async with AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as duplicate_session:
        duplicate_session.add_all(offerings)
        await duplicate_session.flush()

        shared_code = f"global_{suffix}"
        first_payload = DefaultTemplateCreateRequest(
            offering_id=offerings[0].offering_id,
            code=shared_code,
            name="Global email",
            type="EMAIL",
            body="Hello",
        )
        second_payload = DefaultTemplateCreateRequest(
            offering_id=offerings[1].offering_id,
            code=shared_code,
            name="Global letter",
            type="LETTER",
            body="Hello",
        )
        await service.create_template(duplicate_session, ADMIN, first_payload)

        with pytest.raises(ConflictError) as captured:
            await service.create_template(duplicate_session, ADMIN, second_payload)

    assert captured.value.code == "DEFAULT_TEMPLATE_CODE_EXISTS"


@pytest.mark.asyncio
async def test_counts_and_updates_propagate_only_to_inheriting_tenants(
    db_session: AsyncSession,
    test_user: UserAccount,
) -> None:
    suffix = uuid.uuid4().hex[:10]
    customized_tenant = await db_session.get(Tenant, test_user.tenant_id)
    assert customized_tenant is not None
    inheriting_tenant_id = uuid.uuid4()
    offering_id = uuid.uuid4()
    category_id = uuid.uuid4()
    template_id = uuid.uuid4()
    inheriting_tenant = Tenant(
        tenant_id=inheriting_tenant_id,
        org_name="Inheriting Tenant",
        tenant_code=f"INH_{suffix.upper()}",
        contact_name="Inheriting Contact",
        contact_email=f"inheriting-contact-{suffix}@example.test",
        subscription_plan="Free",
        status="ACTIVE",
        created_by_admin_id=customized_tenant.created_by_admin_id,
    )
    inheriting_user = UserAccount(
        tenant_id=inheriting_tenant_id,
        id=uuid.uuid4(),
        display_name="Inheriting Admin",
        email=f"inheriting-{suffix}@example.test",
        username=f"inheriting{suffix[:12]}",
        password_hash="test-only",
        is_active=True,
    )
    offering = Offering(
        offering_id=offering_id,
        code=f"PROP_{suffix.upper()}",
        display_name="Propagation Offering",
        description="Verifies inherited defaults",
        icon_key="mail",
        route_slug=f"propagation-{suffix}",
        sort_order=1002,
        status="ACTIVE",
    )
    category = ConfigCategory(
        category_id=category_id,
        offering_id=offering_id,
        code=f"propagation_{suffix}_email",
        template_type="EMAIL",
        display_name="Email Templates",
        description="Propagation templates",
        icon_key="mail",
        sort_order=10,
        status="ACTIVE",
    )
    template = ConfigTemplate(
        template_id=template_id,
        category_id=category_id,
        code=f"propagation_{suffix}",
        display_name="Propagation template",
        description="A default with one override",
        template_type="EMAIL",
        subject="Hello {{employee_name}}",
        body="Original {{employee_name}}",
        placeholders=[_placeholder()],
        sort_order=10,
        is_active=True,
        version=1,
    )
    active_from = datetime.now(UTC) - timedelta(days=1)
    entitlements = [
        TenantOffering(
            tenant_id=customized_tenant.tenant_id,
            offering_id=offering_id,
            licensed_by_admin_id=customized_tenant.created_by_admin_id,
            status="ACTIVE",
            starts_at=active_from,
        ),
        TenantOffering(
            tenant_id=inheriting_tenant_id,
            offering_id=offering_id,
            licensed_by_admin_id=customized_tenant.created_by_admin_id,
            status="ACTIVE",
            starts_at=active_from,
        ),
    ]
    override = TenantConfigOverride(
        tenant_id=customized_tenant.tenant_id,
        template_id=template_id,
        subject="Custom {{employee_name}}",
        body="Tenant custom {{employee_name}}",
        updated_by_user_id=test_user.user_id,
    )
    # These models intentionally do not define ORM relationships, so stage
    # each foreign-key layer explicitly for a deterministic fixture insert.
    db_session.add_all([inheriting_tenant, offering])
    await db_session.flush()
    db_session.add_all([inheriting_user, category])
    await db_session.flush()
    db_session.add(template)
    await db_session.flush()
    db_session.add_all([*entitlements, override])
    await db_session.flush()

    before = await repository.get_detail(db_session, template.template_id)
    assert before is not None
    assert before.inheriting_tenant_count == 1
    assert before.customized_tenant_count == 1

    await service.update_template(
        db_session,
        ADMIN,
        template.template_id,
        DefaultTemplateUpdateRequest(
            expected_version=1,
            body="Updated platform {{employee_name}}",
        ),
    )
    customized = await tenant_configuration_service.get_effective_template(
        db_session,
        Principal(
            type="user",
            id=test_user.user_id,
            email=test_user.email,
            tenant_id=test_user.tenant_id,
            role="Tenant Admin",
            tenant_status="ACTIVE",
        ),
        template.template_id,
    )
    inherited = await tenant_configuration_service.get_effective_template(
        db_session,
        Principal(
            type="user",
            id=inheriting_user.user_id,
            email=inheriting_user.email,
            tenant_id=inheriting_tenant.tenant_id,
            role="Tenant Admin",
            tenant_status="ACTIVE",
        ),
        template.template_id,
    )

    assert customized.body == "Tenant custom {{employee_name}}"
    assert customized.default_body == "Updated platform {{employee_name}}"
    assert inherited.body == "Updated platform {{employee_name}}"
    assert inherited.is_customized is False
