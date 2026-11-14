# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.base** contains low-level tools for higher-level parts of the
library.
"""

import typing

from . import cmd, matrix, plugins, registry, uname

__all__ = ["cmd", "matrix", "plugins", "registry", "uname", "path_get"]


def path_get(
    structure: typing.Union[dict, list], dotted_path: str, default: typing.Any = None
):
    """
    Look up a value in nested dictionaries and lists, e.g.
    ``with.github.actions`` in a mustache context, or ``include.0.os``.

    :param structure: outermost dictionary or list
    :param dotted_path: keys of each level, separated with dots; for lists,
        the key is the index of the item
    :param default: value returned, if any of the keys is missing
    :returns: the value, or ``default``
    """
    ctx: typing.Any = structure
    for name in dotted_path.split("."):
        if isinstance(ctx, dict):
            try:
                ctx = ctx[name]
                continue
            except KeyError:
                return default

        if isinstance(ctx, (list, tuple)):
            try:
                ctx = ctx[int(name)]
                continue
            except (ValueError, IndexError):
                return default

        return default

    return ctx
