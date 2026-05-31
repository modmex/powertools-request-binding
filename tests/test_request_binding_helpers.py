import inspect

from modmex import BaseModel

from powertools_request_binding.middleware import _request_body_to_args, _request_params_to_args
from powertools_request_binding.params import Body, ModelField, Path


class TodoPayload(BaseModel):
    title: str
    completed: bool


def test_request_params_to_args_validates_path_params():
    field = ModelField(
        name="todo_id",
        param=Path(annotation=int, alias="todo_id", default=inspect.Signature.empty),
    )

    values, errors = _request_params_to_args([field], {"todo_id": "10"}, source="path")

    assert errors == []
    assert values == {"todo_id": 10}


def test_request_body_to_args_builds_model_for_single_body_param():
    field = ModelField(
        name="payload",
        param=Body(annotation=TodoPayload, alias="payload", default=inspect.Signature.empty),
    )

    values, errors = _request_body_to_args([field], {"title": 123, "completed": "true"})

    assert errors == []
    assert isinstance(values["payload"], TodoPayload)
    assert values["payload"].title == "123"
    assert values["payload"].completed is True
