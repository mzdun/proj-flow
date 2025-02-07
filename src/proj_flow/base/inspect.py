# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.base.inspect** provides unified access to function and class
metadata used in argument parser, command and step metadata.
"""

import inspect
import typing
from dataclasses import dataclass


class Function(typing.Protocol):
    """Replacement for :py:func:`callable` as universal argument type."""

    __name__: str

    def __call__(self, **kwarg) -> typing.Any: ...


@dataclass
class Argument:
    """Extracted argument type"""

    #: Name of the argument
    name: str

    #: The type of the argument. If type was :py:class:`typing.Annotated`, then
    #: this is the first argument to that annotation.
    type: type

    #: The list of metadata attached to the :py:class:`typing.Annotated`, if
    #: there was any.
    metadata: typing.List[typing.Any]


def signature(call: Function) -> typing.Generator[Argument, None, None]:
    """
    Extract the arguments from the function and produces list of
    :class:`Argument` objects.

    :param call: Function to analyse.
    :returns: List of the parameters, in order they appeared in the definition.
    """

    signature = inspect.signature(call)

    for param_name, param in signature.parameters.items():
        annotation = param.annotation

        if typing.get_origin(annotation) is not typing.Annotated:
            yield Argument(name=param_name, type=annotation, metadata=[])
            continue

        anno_args = typing.get_args(annotation)
        if len(anno_args) == 0:
            yield Argument(name=param_name, type=type(None), metadata=[])
            continue

        origin = anno_args[0]
        metadata = list(anno_args[1:])

        yield Argument(name=param_name, type=origin, metadata=metadata)


def type_name(t: type) -> str:
    """
    Converts a type to simplified string representing that type.

    :param t: Type to stringify.
    :returns: String representing the type.
    """

    if t == type(None):
        return "None"

    if type(t) == type:
        return t.__name__

    origin = typing.get_origin(t)

    if origin is typing.Union:
        args = typing.get_args(t)
        names: typing.List[str] = []
        for arg in args:
            name = type_name(arg)
            names.append(name)
        return " | ".join(names)

    if origin is None:
        return "?"

    if origin in [list, type, dict]:
        args = typing.get_args(t)
        arg_list = ", ".join(type_name(arg) for arg in args)
        return f"{origin.__name__}[{arg_list}]"

    args = typing.get_args(t)
    arg_list = ", ".join(type_name(arg) for arg in args)
    if arg_list:
        return f"{origin.__name__}[{arg_list}]"

    return typing.cast(str, origin.__name__)
