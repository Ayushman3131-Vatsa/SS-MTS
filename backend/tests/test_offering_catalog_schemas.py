import pytest
from pydantic import ValidationError

from app.schemas.offering import OfferingCreateRequest, OfferingUpdateRequest


def test_offering_create_normalizes_identifiers() -> None:
    payload = OfferingCreateRequest(
        code=" TASK_MANAGEMENT ",
        display_name=" Task Management ",
        description=" Projects and tasks ",
        icon_key=" clipboard-check ",
        route_slug=" task-management ",
        sort_order=20,
    )

    assert payload.code == "TASK_MANAGEMENT"
    assert payload.display_name == "Task Management"
    assert payload.route_slug == "task-management"
    assert payload.status == "INACTIVE"


def test_offering_update_rejects_explicit_null_values() -> None:
    with pytest.raises(ValidationError, match="cannot be null"):
        OfferingUpdateRequest(display_name=None)
