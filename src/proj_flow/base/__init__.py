# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.base** contains low-level tools for higher-level parts of the
library.
"""

import typing

from . import cmd, matrix, plugins, registry, uname

__all__ = ["cmd", "matrix", "plugins", "registry", "uname"]


def path_get(
    structure: typing.Union[dict, list], dotted_path: str, default: typing.Any = None
):
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
                index = int(name)
            except ValueError:
                return default
            except IndexError:
                return default

        return default

    return ctx
