import json
from copy import deepcopy
from typing import Annotated, Any

from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, APIGatewayRestResolver
from aws_lambda_powertools.event_handler.depends import Depends
from modmex import BaseModel

from powertools_request_binding import Body, Query, RequestBindingMiddleware


class TodoPayload(BaseModel):
    title: str
    completed: bool


HTTP_REQUEST_CONTEXT = {
    "accountId": "123456789012",
    "apiId": "api-id",
    "domainName": "id.execute-api.us-east-1.amazonaws.com",
    "domainPrefix": "id",
    "http": {
        "method": "POST",
        "path": "/todos/202",
        "protocol": "HTTP/1.1",
        "sourceIp": "127.0.0.1",
        "userAgent": "pytest",
    },
    "requestId": "test-http-request-id",
    "routeKey": "POST /todos/{todo_id}",
    "stage": "$default",
    "time": "31/May/2026:10:00:00 +0000",
    "timeEpoch": 1780212000000,
}


def _build_rest_event(
    *,
    path: str,
    path_todo_id: str,
    body: dict[str, Any],
    query_string_parameters: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "resource": "/todos/{todo_id}",
        "path": path,
        "httpMethod": "POST",
        "headers": {"content-type": "application/json"},
        "queryStringParameters": query_string_parameters if query_string_parameters is not None else {"enabled": "true"},
        "pathParameters": {"todo_id": path_todo_id},
        "requestContext": {"requestId": "test-request-id", "stage": "dev"},
        "body": json.dumps(body),
        "isBase64Encoded": False,
    }


def _build_http_event(
    *,
    route_key: str,
    raw_path: str,
    method: str,
    body: dict[str, Any] | None = None,
    query_string_parameters: dict[str, str] | None = None,
    path_todo_id: str | None = None,
) -> dict[str, Any]:
    request_context = deepcopy(HTTP_REQUEST_CONTEXT)
    request_context["http"]["method"] = method
    request_context["http"]["path"] = raw_path
    request_context["routeKey"] = route_key

    event: dict[str, Any] = {
        "version": "2.0",
        "routeKey": route_key,
        "rawPath": raw_path,
        "rawQueryString": "",
        "cookies": [],
        "headers": {"content-type": "application/json"},
        "queryStringParameters": query_string_parameters if query_string_parameters is not None else {},
        "requestContext": request_context,
        "isBase64Encoded": False,
    }

    if path_todo_id is not None:
        event["pathParameters"] = {"todo_id": path_todo_id}

    if body is not None:
        event["body"] = json.dumps(body)

    if query_string_parameters:
        event["rawQueryString"] = "&".join(f"{k}={v}" for k, v in query_string_parameters.items())

    return event


def test_request_binding_middleware_injects_for_api_gateway_rest_resolver():
    app = APIGatewayRestResolver()
    app.use(middlewares=[RequestBindingMiddleware()])

    @app.post("/todos/<todo_id>")
    def create_todo(
        todo_id: int,
        payload: Annotated[TodoPayload, Body()],
        enabled: Annotated[bool | None, Query()] = None,
    ):
        return {
            "todo_id": todo_id,
            "enabled": enabled,
            "title": payload.title,
            "completed": payload.completed,
            "types": {
                "todo_id": type(todo_id).__name__,
                "enabled": type(enabled).__name__,
                "payload": type(payload).__name__,
            },
        }

    event = _build_rest_event(
        path="/todos/101",
        path_todo_id="101",
        body={"title": 123, "completed": "false"},
        query_string_parameters={"enabled": "true"},
    )

    response = app.resolve(event, {})

    assert response["statusCode"] == 200
    body = json.loads(response["body"])

    assert body["todo_id"] == 101
    assert body["enabled"] is True
    assert body["title"] == "123"
    assert body["completed"] is False
    assert body["types"] == {"todo_id": "int", "enabled": "bool", "payload": "TodoPayload"}


def test_request_binding_middleware_injects_for_api_gateway_http_resolver():
    app = APIGatewayHttpResolver()
    app.use(middlewares=[RequestBindingMiddleware()])

    @app.post("/todos/<todo_id>")
    def create_todo(
        todo_id: int,
        payload: Annotated[TodoPayload, Body()],
        enabled: Annotated[bool | None, Query()] = None,
    ):
        return {
            "todo_id": todo_id,
            "enabled": enabled,
            "title": payload.title,
            "completed": payload.completed,
            "types": {
                "todo_id": type(todo_id).__name__,
                "enabled": type(enabled).__name__,
                "payload": type(payload).__name__,
            },
        }

    event = _build_http_event(
        route_key="POST /todos/{todo_id}",
        raw_path="/todos/202",
        method="POST",
        body={"title": 456, "completed": "true"},
        query_string_parameters={"enabled": "true"},
        path_todo_id="202",
    )

    response = app.resolve(event, {})

    assert response["statusCode"] == 200
    body = json.loads(response["body"])

    assert body["todo_id"] == 202
    assert body["enabled"] is True
    assert body["title"] == "456"
    assert body["completed"] is True
    assert body["types"] == {"todo_id": "int", "enabled": "bool", "payload": "TodoPayload"}


def test_request_binding_middleware_returns_422_for_invalid_path_rest_resolver():
    app = APIGatewayRestResolver()
    app.use(middlewares=[RequestBindingMiddleware()])

    @app.post("/todos/<todo_id>")
    def create_todo(
        todo_id: int,
        payload: Annotated[TodoPayload, Body()],
        enabled: Annotated[bool | None, Query()] = None,
    ):
        return {"ok": True, "todo_id": todo_id, "enabled": enabled, "title": payload.title}

    event = _build_rest_event(
        path="/todos/not-an-int",
        path_todo_id="not-an-int",
        body={"title": "hello", "completed": "true"},
        query_string_parameters={"enabled": "true"},
    )

    response = app.resolve(event, {})

    assert response["statusCode"] == 422
    body = json.loads(response["body"])
    assert body["statusCode"] == 422
    assert body["detail"][0]["loc"] == ["path", "todo_id"]
    assert body["detail"][0]["type"] == "type_error"


def test_request_binding_middleware_returns_422_for_invalid_body_http_resolver():
    app = APIGatewayHttpResolver()
    app.use(middlewares=[RequestBindingMiddleware()])

    @app.post("/todos/<todo_id>")
    def create_todo(
        todo_id: int,
        payload: Annotated[TodoPayload, Body()],
        enabled: Annotated[bool | None, Query()] = None,
    ):
        return {"ok": True, "todo_id": todo_id, "enabled": enabled, "title": payload.title}

    event = _build_http_event(
        route_key="POST /todos/{todo_id}",
        raw_path="/todos/202",
        method="POST",
        body={"title": 456},
        query_string_parameters={"enabled": "true"},
        path_todo_id="202",
    )

    response = app.resolve(event, {})

    assert response["statusCode"] == 422
    body = json.loads(response["body"])
    assert body["statusCode"] == 422
    assert body["detail"][0]["loc"] == ["body", "payload"]
    assert body["detail"][0]["type"] == "type_error"


def test_request_binding_middleware_keeps_powertools_depends_injection_working():
    app = APIGatewayHttpResolver()
    app.use(middlewares=[RequestBindingMiddleware()])

    class FakeTable:
        def scan(self) -> dict[str, list[dict[str, Any]]]:
            return {"Items": [{"id": "order-1"}]}

    def get_dynamodb_table() -> FakeTable:
        return FakeTable()

    @app.get("/orders")
    def list_orders(table: Annotated[Any, Depends(get_dynamodb_table)]):
        return table.scan()["Items"]

    event = _build_http_event(
        route_key="GET /orders",
        raw_path="/orders",
        method="GET",
    )
    event["headers"] = {}

    response = app.resolve(event, {})

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body == [{"id": "order-1"}]
