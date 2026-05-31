from __future__ import annotations

import inspect
from typing import Any, Mapping, Sequence

from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, APIGatewayRestResolver, Response
from aws_lambda_powertools.event_handler.middlewares import BaseMiddlewareHandler, NextMiddleware
from aws_lambda_powertools.event_handler.api_gateway import Route
from aws_lambda_powertools.event_handler.openapi.exceptions import RequestValidationError

from .dependant import get_dependant
from .params import ModelField, Param
from modmex.errors import ValidationError
from .validation import validate_value


class RequestBindingMiddleware(BaseMiddlewareHandler):
    def handler(
        self,
        app: APIGatewayRestResolver | APIGatewayHttpResolver,
        next_middleware: NextMiddleware,
    ) -> Response:
        route: Route = app.context["_route"]

        values: dict[str, Any] = {}
        errors: list[Any] = []

        dependant = get_dependant(path=route.openapi_path, call=route.func)

        if dependant.path_params:
            path_values, path_errors = _request_params_to_args(
                dependant.path_params,
                app.context.get("_route_args") or {},
                source="path",
            )
            values.update(path_values)
            errors.extend(path_errors)

        if dependant.body_params:
            body_values, body_errors = _request_body_to_args(
                dependant.body_params,
                app.current_event.json_body,
            )
            values.update(body_values)
            errors.extend(body_errors)

        if dependant.query_params:
            query_values, query_errors = _request_query_to_args(
                dependant.query_params,
                app.current_event.query_string_parameters,
            )
            values.update(query_values)
            errors.extend(query_errors)

        if dependant.header_params:
            header_values, header_errors = _request_params_to_args(
                dependant.header_params,
                app.current_event.headers or {},
                source="header",
            )
            values.update(header_values)
            errors.extend(header_errors)

        if errors:
            raise RequestValidationError(errors=errors, body=app.current_event.body)

        app.context["_route_args"] = values
        return next_middleware(app)

def _request_params_to_args(
    required_params: Sequence[ModelField],
    received_params: Mapping[str, Any] | None,
    source: str,
) -> tuple[dict[str, Any], list[Any]]:
    values: dict[str, Any] = {}
    errors: list[Any] = []
    payload = received_params or {}

    for field in required_params:
        field_info = field.param

        if not isinstance(field_info, Param):
            raise AssertionError(f"Expected Param field_info, got {field_info}")

        value = payload.get(field_info.alias)
        if value is None:
            if _has_default(field_info):
                values[field.name] = field_info.default
            else:
                errors.append({"loc": [source, field_info.alias], "msg": "Field required", "type": "missing"})
            continue

        try:
            values[field.name] = validate_value(field_info.annotation, value, [source, field_info.alias])
        except ValidationError as e:
            errors.extend(e.errors)

    return values, errors


def _request_body_to_args(
    required_params: Sequence[ModelField],
    received_body: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[Any]]:
    values: dict[str, Any] = {}
    errors: list[Any] = []

    for field in required_params:
        field_info = field.param
        if not isinstance(field_info, Param):
            raise AssertionError(f"Expected Param field_info, got {field_info}")

        if received_body is None:
            if _has_default(field_info):
                values[field.name] = field_info.default
            else:
                errors.append({"loc": ["body", field_info.alias], "msg": "Field required", "type": "missing"})
            continue

        body_value: Any
        if len(required_params) == 1:
            body_value = received_body
        elif isinstance(received_body, Mapping):
            body_value = received_body.get(field_info.alias)
        else:
            body_value = None

        if body_value is None:
            if _has_default(field_info):
                values[field.name] = field_info.default
            else:
                errors.append({"loc": ["body", field_info.alias], "msg": "Field required", "type": "missing"})
            continue

        try:
            values[field.name] = validate_value(field_info.annotation, body_value, ["body", field_info.alias])
        except ValidationError as e:
            errors.extend(e.errors)

    return values, errors

def _request_query_to_args(
    required_params: Sequence[ModelField],
    received_query_params: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], list[Any]]:
    return _request_params_to_args(required_params, received_query_params, source="query")


def _has_default(field: Param) -> bool:
    return field.default is not inspect.Signature.empty
