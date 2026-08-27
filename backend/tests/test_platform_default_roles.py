from app.main import app as production_app
from app.modules.platform_default_roles.clone import TemplateChoice, pick_bootstrap_templates
from app.modules.platform_default_roles.schemas import DefaultRoleCreateRequest, DefaultRoleUpdateRequest
from pydantic import ValidationError
import pytest
import uuid


def test_default_role_create_normalizes_code() -> None:
    payload = DefaultRoleCreateRequest(role_name="Task manager", role_code="task manager")
    assert payload.role_code == "TASK_MANAGER"


def test_default_role_update_requires_a_change() -> None:
    with pytest.raises(ValidationError):
        DefaultRoleUpdateRequest(version=1)


def test_openapi_documents_default_role_routes() -> None:
    schema = production_app.openapi()
    assert "/platform/default-roles" in schema["paths"]
    assert "/platform/default-roles/{role_id}" in schema["paths"]
    assert "/platform/default-roles/pages" in schema["paths"]


def test_bootstrap_picks_one_admin_style_role_per_module() -> None:
    core_admin = TemplateChoice(
        role_id=uuid.uuid4(),
        role_code="TENANT_ADMIN",
        role_name="Tenant Admin",
        offering_id=None,
        module_scope="CORE",
        is_system=True,
        modify_count=4,
    )
    core_viewer = TemplateChoice(
        role_id=uuid.uuid4(),
        role_code="WORKSPACE_VIEWER",
        role_name="Workspace Viewer",
        offering_id=None,
        module_scope="CORE",
        is_system=False,
        modify_count=0,
    )
    offering_id = uuid.uuid4()
    task_manager = TemplateChoice(
        role_id=uuid.uuid4(),
        role_code="TASK_MANAGER",
        role_name="Task Manager",
        offering_id=offering_id,
        module_scope="TASK_MANAGEMENT",
        is_system=True,
        modify_count=6,
    )
    task_viewer = TemplateChoice(
        role_id=uuid.uuid4(),
        role_code="TASK_VIEWER",
        role_name="Task Viewer",
        offering_id=offering_id,
        module_scope="TASK_MANAGEMENT",
        is_system=True,
        modify_count=0,
    )
    picked = pick_bootstrap_templates([core_viewer, core_admin, task_viewer, task_manager])
    assert [item.role_code for item in picked] == ["TENANT_ADMIN", "TASK_MANAGER"]


def test_default_role_create_normalizes_code() -> None:
    payload = DefaultRoleCreateRequest(role_name="Task manager", role_code="task manager")
    assert payload.role_code == "TASK_MANAGER"


def test_default_role_update_requires_a_change() -> None:
    with pytest.raises(ValidationError):
        DefaultRoleUpdateRequest(version=1)


def test_openapi_documents_default_role_routes() -> None:
    schema = production_app.openapi()
    assert "/platform/default-roles" in schema["paths"]
    assert "/platform/default-roles/{role_id}" in schema["paths"]
    assert "/platform/default-roles/pages" in schema["paths"]
