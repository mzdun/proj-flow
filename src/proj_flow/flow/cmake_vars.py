# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.flow.cmake_vars** resolves the values of the CMake variables
listed in the ``cmake.vars`` section of the flow config.
"""

from typing import Any, Optional

from proj_flow.api import env


def _same_value(value, expected: str) -> bool:
    if isinstance(value, bool):
        return str(value).lower() == expected.lower()
    return value is not None and str(value) == expected


def cmake_value(reference: str, config: env.Config, rt: env.Runtime) -> str:
    """
    Value of a CMake variable from the ``cmake.vars`` section of the flow
    config.

    :param reference: ``config:<path>`` or ``runtime:<name>``, taken from
        the config of the run or from the runtime, or a literal value; with a
        ``?`` in front, the result is ``ON``, if the value is true, and
        ``OFF`` otherwise. A flag may also end with ``=<value>``, e.g.
        ``?config:sanitizer=thread``; then it is ``ON``, if the value is
        equal to that one.
    :param config: the config of the run
    :param rt: the runtime of the run
    """
    value: Any = reference

    is_flag = value.startswith("?")
    expected: Optional[str] = None
    if is_flag:
        value = value[1:]
        if "=" in value:
            value, expected = value.split("=", 1)

    if value.startswith("config:"):
        value = config.get_path(value[len("config:") :])
    elif value.startswith("runtime:"):
        value = getattr(rt, value[len("runtime:") :], None)

    if not is_flag:
        return str(value)
    if expected is not None:
        return "ON" if _same_value(value, expected) else "OFF"
    return "ON" if value else "OFF"
