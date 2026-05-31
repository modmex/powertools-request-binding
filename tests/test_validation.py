import pytest

from modmex import BaseModel
from modmex.errors import ValidationError

from powertools_request_binding.validation import validate_value


class TodoPayload(BaseModel):
    title: str
    completed: bool


def test_validate_value_coerces_primitive_types():
    assert validate_value(int, "42", ["query", "page"]) == 42
    assert validate_value(bool, "true", ["query", "enabled"]) is True


def test_validate_value_builds_modmex_models():
    payload = validate_value(
        TodoPayload,
        {"title": 123, "completed": "false"},
        ["body", "payload"],
    )

    assert isinstance(payload, TodoPayload)
    assert payload.title == "123"
    assert payload.completed is False


def test_validate_value_reports_missing_required_field():
    with pytest.raises(ValidationError):
        validate_value(int, None, ["path", "todo_id"])
