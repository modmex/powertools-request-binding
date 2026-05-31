from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Annotated, get_args, get_origin
from uuid import UUID

from aws_lambda_powertools.event_handler.depends import Depends as PowertoolsDepends


class Param:
    def __init__(
        self,
        *,
        annotation: Any = None,
        default: Any = inspect.Signature.empty,
        alias: str | None = None,
        **metadata: Any,
    ) -> None:
        self.annotation = annotation
        self.default = default
        self.alias = alias
        self.metadata = metadata

    def clone_with(self, *, annotation: Any, default: Any) -> "Param":
        return type(self)(annotation=annotation, default=default, alias=self.alias, **self.metadata)


@dataclass
class ModelField:
    param: Param
    name: str


class Body(Param):
    pass


class Query(Param):
    pass


class Path(Param):
    pass


class Header(Param):
    pass


_SCALAR_TYPES = {
    str,
    int,
    float,
    bool,
    Decimal,
    date,
    datetime,
    time,
    UUID,
}


def analyze_param(
    param_name: str,
    annotation: Any,
    value: Any,
    is_path_param: bool,
    is_response_param: bool,
) -> ModelField:
    del is_response_param

    if _is_powertools_dependency(annotation):
        # Let Powertools dependency injection resolve this parameter.
        return None

    param, type_annotation = get_param_and_type_annotation(annotation, value)

    if param is None:
        if is_path_param:
            param = Path(annotation=type_annotation, default=value)
        elif _is_scalar_annotation(type_annotation):
            param = Query(annotation=type_annotation, default=value)
        else:
            param = Body(annotation=type_annotation, default=value)

    param.alias = param_name
    return ModelField(param=param, name=param_name)


def get_param_and_type_annotation(annotation: Any, value: Any) -> tuple[Param | None, Any]:
    param: Param | None = None
    type_annotation: Any = Any

    if annotation is not inspect.Signature.empty:
        if get_origin(annotation) is Annotated:
            param, type_annotation = get_param_annotated_type(annotation, value)
        else:
            type_annotation = annotation

    return param, type_annotation


def get_param_annotated_type(annotation: Any, value: Any) -> tuple[Param | None, Any]:
    param: Param | None = None
    annotated_args = get_args(annotation)
    type_annotation = annotated_args[0]
    param_annotations = [arg for arg in annotated_args[1:] if isinstance(arg, Param)]

    if len(param_annotations) > 1:
        raise AssertionError("Only one Param can be used per parameter")

    param_annotation = next(iter(param_annotations), None)
    if isinstance(param_annotation, Param):
        param = param_annotation.clone_with(annotation=type_annotation, default=value)

    return param, type_annotation


def _is_scalar_annotation(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is None:
        return annotation in _SCALAR_TYPES

    if origin is Annotated:
        return _is_scalar_annotation(get_args(annotation)[0])

    # Handle Optional[T] / Union[T, None]
    union_args = [arg for arg in get_args(annotation) if arg is not type(None)]
    if union_args and len(union_args) != len(get_args(annotation)):
        return all(_is_scalar_annotation(arg) for arg in union_args)

    return False


def _is_powertools_dependency(annotation: Any) -> bool:
    if get_origin(annotation) is not Annotated:
        return False

    metadata = get_args(annotation)[1:]
    return any(isinstance(item, PowertoolsDepends) for item in metadata)