import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.common.deps import Principal
from app.common.template_renderer import render_template
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.config import get_settings
from app.models.config_category import ConfigCategory
from app.models.config_template import ConfigTemplate
from app.models.offering import Offering
from app.models.tenant import Tenant
from app.models.tenant_config_override import TenantConfigOverride
from app.models.tenant_offering import TenantOffering
from app.modules.configurations import repository, service
from app.schemas.configuration import TemplateOverrideRequest


def _principal_for(test_user) -> Principal:
    return Principal(
        type="user",
        id=test_user.user_id,
        email=test_user.email,
        tenant_id=test_user.tenant_id,
        role="Tenant Admin",
        tenant_status="ACTIVE",
    )


async def _grant_active_entitlement(
    db_session: AsyncSession,
    test_user,
    offering: Offering,
) -> TenantOffering:
    tenant = await db_session.get(Tenant, test_user.tenant_id)
    assert tenant is not None
    entitlement = TenantOffering(
        tenant_id=test_user.tenant_id,
        offering_id=offering.offering_id,
        licensed_by_admin_id=tenant.created_by_admin_id,
        status="ACTIVE",
        starts_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(entitlement)
    await db_session.flush()
    return entitlement


async def _seed_tenant_template(
    db_session: AsyncSession,
    test_user,
) -> tuple[ConfigCategory, ConfigTemplate]:
    unique = uuid.uuid4().hex[:12]
    tenant = await db_session.get(Tenant, test_user.tenant_id)
    assert tenant is not None

    offering = Offering(
        code=f"CONFIG_{unique.upper()}",
        display_name=f"Configuration Test {unique}",
        description="Configuration regression test offering",
        icon_key="mail",
        route_slug=f"configuration-{unique}",
        sort_order=10,
    )
    db_session.add(offering)
    await db_session.flush()

    category = ConfigCategory(
        offering_id=offering.offering_id,
        code=f"configuration_{unique}",
        display_name="Email Templates",
        description="Configuration regression templates",
        icon_key="mail",
        template_type="EMAIL",
    )
    db_session.add(category)
    await db_session.flush()

    template = ConfigTemplate(
        category_id=category.category_id,
        code=f"configuration_email_{unique}",
        display_name="Configuration Email",
        description="Configuration regression template",
        template_type="EMAIL",
        subject="Initial subject {{name}}",
        body="Initial body {{name}}",
        placeholders=[
            {
                "key": "name",
                "label": "Name",
                "sample_value": "Taylor",
                "required": True,
            }
        ],
    )
    entitlement = TenantOffering(
        tenant_id=test_user.tenant_id,
        offering_id=offering.offering_id,
        licensed_by_admin_id=tenant.created_by_admin_id,
        status="ACTIVE",
        starts_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add_all([template, entitlement])
    await db_session.flush()
    return category, template


@pytest.mark.asyncio
async def test_render_template_default(db_session: AsyncSession, test_user):
    """Test rendering a platform default template when no override exists."""
    # 1. Create dummy offering, category, template
    offering = Offering(
        code="TEST_OFFERING",
        display_name="Test Offering",
        description="Testing",
        icon_key="users",
        route_slug="test-offering",
        sort_order=1,
    )
    db_session.add(offering)
    await db_session.flush()

    category = ConfigCategory(
        offering_id=offering.offering_id,
        code="test_category",
        display_name="Test Category",
        description="Test Category Desc",
        icon_key="mail",
        template_type="EMAIL",
    )
    db_session.add(category)
    await db_session.flush()

    template = ConfigTemplate(
        category_id=category.category_id,
        code="test_welcome_email",
        display_name="Test Welcome Email",
        description="Welcome email for test",
        template_type="EMAIL",
        subject="Welcome {{name}} to {{company}}!",
        body="Hello {{name}},\n\nWelcome to {{company}} as {{role}}.",
        placeholders=[
            {"key": "name", "label": "Full Name", "sample_value": "John"},
            {"key": "company", "label": "Company", "sample_value": "Acme"},
            {"key": "role", "label": "Role", "sample_value": "Engineer"},
        ],
    )
    db_session.add(template)
    await db_session.flush()
    await _grant_active_entitlement(db_session, test_user, offering)

    # 2. Render template for an entitled tenant
    rendered = await render_template(
        db_session,
        tenant_id=test_user.tenant_id,
        template_code="test_welcome_email",
        context={"name": "Alice", "company": "SmartSkale", "role": "Architect"},
    )

    assert rendered.is_customized is False
    assert rendered.subject == "Welcome Alice to SmartSkale!"
    assert rendered.body == "Hello Alice,\n\nWelcome to SmartSkale as Architect."


@pytest.mark.asyncio
async def test_render_template_with_tenant_override(db_session: AsyncSession, test_user):
    """Test rendering a template when a tenant override is present."""
    # 1. Create dummy offering, category, template
    offering = Offering(
        code="TEST_OFFERING_2",
        display_name="Test Offering 2",
        description="Testing 2",
        icon_key="clipboard-check",
        route_slug="test-offering-2",
        sort_order=2,
    )
    db_session.add(offering)
    await db_session.flush()

    category = ConfigCategory(
        offering_id=offering.offering_id,
        code="test_category_2",
        display_name="Test Category 2",
        description="Test Category Desc 2",
        icon_key="mail",
        template_type="EMAIL",
    )
    db_session.add(category)
    await db_session.flush()

    template = ConfigTemplate(
        category_id=category.category_id,
        code="test_task_assigned",
        display_name="Test Task Assigned",
        template_type="EMAIL",
        subject="Task Assigned: {{task_title}}",
        body="Hi {{assignee}}, task {{task_title}} is assigned to you.",
    )
    db_session.add(template)
    await db_session.flush()
    await _grant_active_entitlement(db_session, test_user, offering)

    # 2. Create tenant override for test_user's tenant
    override = TenantConfigOverride(
        tenant_id=test_user.tenant_id,
        template_id=template.template_id,
        subject="[CUSTOM] Task Assigned: {{task_title}}",
        body="CUSTOM BODY: Hey {{assignee}}, please check {{task_title}} ASAP!",
        updated_by_user_id=test_user.user_id,
    )
    db_session.add(override)
    await db_session.flush()

    # 3. Render template
    rendered = await render_template(
        db_session,
        tenant_id=test_user.tenant_id,
        template_code="test_task_assigned",
        context={"assignee": "Bob", "task_title": "Fix Auth Bug"},
    )

    assert rendered.is_customized is True
    assert rendered.subject == "[CUSTOM] Task Assigned: Fix Auth Bug"
    assert rendered.body == "CUSTOM BODY: Hey Bob, please check Fix Auth Bug ASAP!"


@pytest.mark.asyncio
async def test_default_update_preserves_snapshotted_tenant_text_and_override_id(
    db_session: AsyncSession,
    test_user,
):
    """A first partial override owns both text fields before defaults change."""
    _, template = await _seed_tenant_template(db_session, test_user)
    principal = _principal_for(test_user)

    saved = await service.save_override(
        db_session,
        principal,
        template.template_id,
        TemplateOverrideRequest(subject="Tenant subject {{name}}"),
    )
    override = await repository.get_tenant_override(
        db_session, test_user.tenant_id, template.template_id,
    )
    assert override is not None
    override_id = override.override_id
    assert saved.subject == "Tenant subject {{name}}"
    assert saved.body == "Initial body {{name}}"
    assert override.subject == "Tenant subject {{name}}"
    assert override.body == "Initial body {{name}}"

    template.subject = "Newest platform subject {{name}}"
    template.body = "Newest platform body {{name}}"
    await db_session.flush()

    effective = await service.get_effective_template(
        db_session, principal, template.template_id,
    )
    rendered = await render_template(
        db_session,
        tenant_id=test_user.tenant_id,
        template_code=template.code,
        context={"name": "Alex"},
    )
    same_override = await repository.get_tenant_override(
        db_session, test_user.tenant_id, template.template_id,
    )

    assert same_override is not None
    assert same_override.override_id == override_id
    assert effective.subject == "Tenant subject {{name}}"
    assert effective.body == "Initial body {{name}}"
    assert effective.default_subject == "Newest platform subject {{name}}"
    assert effective.default_body == "Newest platform body {{name}}"
    assert rendered.subject == "Tenant subject Alex"
    assert rendered.body == "Initial body Alex"


@pytest.mark.asyncio
async def test_reset_override_reveals_newest_platform_default(
    db_session: AsyncSession,
    test_user,
):
    _, template = await _seed_tenant_template(db_session, test_user)
    principal = _principal_for(test_user)
    await service.save_override(
        db_session,
        principal,
        template.template_id,
        TemplateOverrideRequest(body="Tenant body {{name}}"),
    )

    template.subject = "Newest platform subject {{name}}"
    template.body = "Newest platform body {{name}}"
    await db_session.flush()

    before_reset = await service.get_effective_template(
        db_session, principal, template.template_id,
    )
    assert before_reset.subject == "Initial subject {{name}}"
    assert before_reset.body == "Tenant body {{name}}"

    reset = await service.reset_override(db_session, principal, template.template_id)

    assert reset.is_customized is False
    assert reset.subject == "Newest platform subject {{name}}"
    assert reset.body == "Newest platform body {{name}}"
    assert await repository.get_tenant_override(
        db_session, test_user.tenant_id, template.template_id,
    ) is None


@pytest.mark.asyncio
async def test_template_list_returns_effective_tenant_subject(
    db_session: AsyncSession,
    test_user,
):
    category, template = await _seed_tenant_template(db_session, test_user)
    principal = _principal_for(test_user)
    await service.save_override(
        db_session,
        principal,
        template.template_id,
        TemplateOverrideRequest(subject="Tenant list subject {{name}}"),
    )
    template.subject = "New platform list subject {{name}}"
    await db_session.flush()

    templates = await service.list_templates(
        db_session, principal, category.category_id,
    )

    assert len(templates) == 1
    assert templates[0].template_id == template.template_id
    assert templates[0].subject == "Tenant list subject {{name}}"
    assert templates[0].is_customized is True


@pytest.mark.asyncio
async def test_tenant_override_validates_required_tokens_across_subject_and_body(
    db_session: AsyncSession,
    test_user,
):
    _, template = await _seed_tenant_template(db_session, test_user)
    principal = _principal_for(test_user)

    # The required token remains in the inherited subject, so customizing only
    # the body is valid.
    saved = await service.save_override(
        db_session,
        principal,
        template.template_id,
        TemplateOverrideRequest(body="Tenant body without a token"),
    )
    assert saved.subject == "Initial subject {{name}}"
    assert saved.body == "Tenant body without a token"

    # Removing the token from the complete effective snapshot is rejected.
    with pytest.raises(BusinessRuleError):
        await service.save_override(
            db_session,
            principal,
            template.template_id,
            TemplateOverrideRequest(
                subject="Tenant subject without a token",
                body="Tenant body without a token",
            ),
        )


@pytest.mark.asyncio
async def test_explicit_null_subject_is_frozen_in_override_snapshot(
    db_session: AsyncSession,
    test_user,
):
    _, template = await _seed_tenant_template(db_session, test_user)
    principal = _principal_for(test_user)

    saved = await service.save_override(
        db_session,
        principal,
        template.template_id,
        TemplateOverrideRequest(
            subject=None,
            body="Tenant body {{name}}",
        ),
    )
    assert saved.subject is None

    template.subject = "A later platform subject {{name}}"
    await db_session.flush()

    effective = await service.get_effective_template(
        db_session,
        principal,
        template.template_id,
    )
    assert effective.subject is None


@pytest.mark.asyncio
async def test_runtime_renderer_requires_current_effective_entitlement(
    db_session: AsyncSession,
    test_user,
):
    category, template = await _seed_tenant_template(db_session, test_user)

    with pytest.raises(NotFoundError):
        await render_template(
            db_session,
            tenant_id=uuid.uuid4(),
            template_code=template.code,
            context={"name": "Unlicensed"},
        )

    entitlement = (
        await db_session.execute(
            select(TenantOffering).where(
                TenantOffering.tenant_id == test_user.tenant_id,
                TenantOffering.offering_id == category.offering_id,
            )
        )
    ).scalar_one()
    entitlement.status = "EXPIRED"
    entitlement.ends_at = datetime.now(timezone.utc)
    await db_session.flush()

    with pytest.raises(NotFoundError):
        await render_template(
            db_session,
            tenant_id=test_user.tenant_id,
            template_code=template.code,
            context={"name": "Expired"},
        )


@pytest.mark.asyncio
async def test_runtime_renderer_rejects_tenant_or_catalog_inactive_template(
    db_session: AsyncSession,
    test_user,
):
    category, template = await _seed_tenant_template(db_session, test_user)
    principal = _principal_for(test_user)

    await service.save_override(
        db_session,
        principal,
        template.template_id,
        TemplateOverrideRequest(is_active=False),
    )
    with pytest.raises(NotFoundError):
        await render_template(
            db_session,
            tenant_id=test_user.tenant_id,
            template_code=template.code,
            context={"name": "Disabled"},
        )

    await service.reset_override(db_session, principal, template.template_id)
    category.status = "INACTIVE"
    await db_session.flush()
    with pytest.raises(NotFoundError):
        await render_template(
            db_session,
            tenant_id=test_user.tenant_id,
            template_code=template.code,
            context={"name": "Inactive category"},
        )


@pytest.mark.asyncio
async def test_override_slot_lock_serializes_concurrent_first_writers() -> None:
    engine = create_async_engine(
        get_settings().database_url,
        poolclass=NullPool,
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    tenant_id = uuid.uuid4()
    template_id = uuid.uuid4()
    try:
        async with sessions() as first, sessions() as second:
            await first.begin()
            await second.begin()
            await repository.lock_override_slot(first, tenant_id, template_id)

            waiting_writer = asyncio.create_task(
                repository.lock_override_slot(second, tenant_id, template_id)
            )
            await asyncio.sleep(0.05)
            assert not waiting_writer.done()

            await first.commit()
            await asyncio.wait_for(waiting_writer, timeout=1)
            await second.rollback()
    finally:
        await engine.dispose()
