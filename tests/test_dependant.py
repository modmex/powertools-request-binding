from typing import Annotated

from modmex import BaseModel

from powertools_request_binding.dependant import get_dependant
from powertools_request_binding.params import Body, Header, Query


class TodoPayload(BaseModel):
    title: str
    completed: bool


def handler(
    todo_id: int,
    payload: Annotated[TodoPayload, Body()],
    source: Annotated[str | None, Query()] = None,
    correlation_id: Annotated[str, Header()] = "",
):
    return {"ok": True}


def test_get_dependant_categorizes_handler_parameters():
    dependant = get_dependant(path="/todos/{todo_id}", call=handler)

    assert len(dependant.path_params) == 1
    assert dependant.path_params[0].name == "todo_id"

    assert len(dependant.body_params) == 1
    assert dependant.body_params[0].name == "payload"

    assert len(dependant.query_params) == 1
    assert dependant.query_params[0].name == "source"

    assert len(dependant.header_params) == 1
    assert dependant.header_params[0].name == "correlation_id"
