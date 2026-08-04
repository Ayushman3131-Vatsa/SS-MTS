import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.template_renderer import render_template
from app.models.config_category import ConfigCategory
from app.models.config_template import ConfigTemplate
from app.models.tenant_config_override import TenantConfigOverride
from app.models.offering import Offering


@pytest.mark.asyncio
async def test_render_template_default(db_session: AsyncSession):
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

    # 2. Render template for a dummy tenant ID
    tenant_id = uuid.uuid4()
    rendered = await render_template(
        db_session,
        tenant_id=tenant_id,
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
