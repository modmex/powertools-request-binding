from __future__ import annotations

import inspect
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping, Sequence, get_args, get_origin

from modmex import BaseModel
from modmex.errors import ValidationError
from modmex.validation import (
    bool_validator,
    decimal_validator,
    float_validator,
    int_validator,
    parse_date,
    parse_datetime,
    str_validator,
)


_PRIMITIVE_VALIDATORS = {
    str: str_validator,
    int: int_validator,
    bool: bool_validator,
    float: float_validator,
    datetime: parse_datetime,
    date: parse_date,
    Decimal: decimal_validator,
}


def validate_value(annotation: Any, value: Any, loc: list[Any] | None = None) -> Any:
    location = list(loc or [])

    if annotation is inspect.Signature.empty or annotation is Any:
        return value

    if value is None:
        if _accepts_none(annotation):
            return None
        raise ValidationError(errors=[{"loc": location, "msg": "Field required", "type": "missing"}])

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is not None:
        if str(origin) == "<class 'typing.Annotated'>":
            return validate_value(args[0], value, location)

        if origin in (list, Sequence):
            return [validate_value(args[0], item, location + [idx]) for idx, item in enumerate(value)]

        if origin is tuple:
            if len(args) == 2 and args[1] is Ellipsis:
                return tuple(validate_value(args[0], item, location + [idx]) for idx, item in enumerate(value))
            if len(value) != len(args):
                raise ValidationError(errors=[{"loc": location, "msg": "Tuple length mismatch", "type": "type_error"}])
            return tuple(validate_value(arg, item, location + [idx]) for idx, (arg, item) in enumerate(zip(args, value)))

        if origin is dict:
            key_type, value_type = args
            validated: dict[Any, Any] = {}
            for key, item in value.items():
                valid_key = validate_value(key_type, key, location + ["<key>"])
                validated[valid_key] = validate_value(value_type, item, location + [key])
            return validated

        # Handles Optional[T] and Union[...] for both typing.Union and T | U
        if origin.__module__ == "typing" and origin.__qualname__ == "Union" or str(origin) == "<class 'types.UnionType'>":
            candidate_errors: list[dict[str, Any]] = []
            for candidate in args:
                try:
                    return validate_value(candidate, value, location)
                except ValidationError as exc:
                    candidate_errors.extend(exc.errors)
            raise ValidationError(errors=candidate_errors or [{"loc": location, "msg": "Invalid union type", "type": "type_error"}])

    if _is_literal(annotation):
        if value in get_args(annotation):
            return value
        raise ValidationError(errors=[{"loc": location, "msg": f"Unexpected literal value: {value}", "type": "literal_error"}])

    try:
        if annotation in _PRIMITIVE_VALIDATORS:
            return _PRIMITIVE_VALIDATORS[annotation](value)

        if inspect.isclass(annotation) and issubclass(annotation, Enum):
            return annotation(value)

        if inspect.isclass(annotation) and issubclass(annotation, BaseModel):
            if isinstance(value, annotation):
                return value
            if not isinstance(value, Mapping):
                raise ValidationError(errors=[{"loc": location, "msg": "Expected object", "type": "type_error"}])
            return annotation(**value)

        if isinstance(value, annotation):
            return value

        if isinstance(value, Mapping):
            return annotation(**value)

        return annotation(value)

    except ValidationError as exc:
        raise ValidationError(errors=[_prefix_error(error, location) for error in exc.errors]) from exc
    except (TypeError, ValueError) as exc:
        raise ValidationError(errors=[{"loc": location, "msg": str(exc), "type": "type_error"}]) from exc


def _prefix_error(error: dict[str, Any], prefix: list[Any]) -> dict[str, Any]:
    loc = error.get("loc", [])
    return {
        "loc": [*prefix, *loc],
        "msg": error.get("msg", "Validation error"),
        "type": error.get("type", "type_error"),
    }


def _accepts_none(annotation: Any) -> bool:
    origin = get_origin(annotation)
    if origin is None:
        return annotation is type(None)
    return any(arg is type(None) for arg in get_args(annotation))


def _is_literal(annotation: Any) -> bool:
    origin = get_origin(annotation)
    return getattr(origin, "__qualname__", "") == "Literal"
    