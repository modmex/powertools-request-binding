from __future__ import annotations

import typing
from typing import Any, Callable
import re
import inspect
from .params import Body, Header, ModelField, Path, Query, analyze_param




class Dependant:
    def __init__(self,
                 path_params: list | None = None,
                 query_params: list | None = None,
                 header_params: list | None = None,
                 body_params: list | None = None,
                 name: str | None = None,
                 call: Callable[..., Any] = None,
                 path: str | None = None,
                 ):
        self.path_params = path_params or []
        self.query_params = query_params or []
        self.header_params = header_params or []
        self.body_params = body_params or []
        self.name = name
        self.call = call
        self.path = path


def get_typed_signature(call: Callable[..., Any]) -> inspect.Signature:
    """
    Returns a typed signature for a callable, resolving forward references.

    Parameters
    ----------
    call: Callable[..., Any]
        The callable to get the signature for

    Returns
    -------
    inspect.Signature
        The typed signature
    """
    signature = inspect.signature(call)
    globalns = getattr(call, "__globals__", {})
    localns = dict(globalns)

    try:
        type_hints = typing.get_type_hints(call, globalns=globalns, localns=localns, include_extras=True)
    except Exception:
        type_hints = {}

    typed_params = [
        inspect.Parameter(
            name=param.name,
            kind=param.kind,
            default=param.default,
            annotation=type_hints.get(param.name, param.annotation),
        )
        for param in signature.parameters.values()
    ]

    # If the return annotation is not empty, add it to the signature.
    return_annotation = type_hints.get("return", signature.return_annotation)
    return inspect.Signature(typed_params, return_annotation=return_annotation)


def get_path_param_names(path: str) -> set[str]:
    """
    Returns the path parameter names from a path template. Those are the strings between { and }.

    Parameters
    ----------
    path: str
        The path template

    Returns
    -------
    set[str]
        The path parameter names

    """
    return set(re.findall("{(.*?)}", path))


def get_dependant(
    *,
    path: str,
    call: Callable[..., Any],
    name: str | None = None,
) -> Dependant:
    """
    Returns a dependant model for a handler function. A dependant model is a model that contains
    the parameters and return value of a handler function.

    Parameters
    ----------
    path: str
        The path template
    call: Callable[..., Any]
        The handler function
    name: str, optional
        The name of the handler function

    Returns
    -------
    Dependant
        The dependant model for the handler function
    """
    path_param_names = get_path_param_names(path)
    endpoint_signature = get_typed_signature(call)
    signature_params = endpoint_signature.parameters

    dependant = Dependant(
        call=call,
        name=name,
        path=path,
    )

    for param_name, param in signature_params.items():
        is_path_param = param_name in path_param_names
        param_field = analyze_param(
            param_name=param_name,
            annotation=param.annotation,
            value=param.default,
            is_path_param=is_path_param,
            is_response_param=False,
        )
        if param_field is None:
            continue
        
        if isinstance(param_field.param, Query):
            dependant.query_params.append(param_field)
        if isinstance(param_field.param, Body):
            dependant.body_params.append(param_field)
        if isinstance(param_field.param, Header):
            dependant.header_params.append(param_field)
        if isinstance(param_field.param, Path):
            dependant.path_params.append(param_field)
    return dependant