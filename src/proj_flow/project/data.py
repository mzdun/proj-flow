# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.project.data** supports the ``init`` command.
"""

from typing import Any

from proj_flow.api import ctx


def get_internal(key: str, value: Any = None):
    return ctx.internals.get(key, value)
