# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import collections
import os
from typing import List

import pytest

from proj_flow.api import env

from ..capture import Capture


def test_default_compiler():
    saved_platform = env.platform
    saved_compilers = env._flow_config_default_compiler
    env.platform = "os-name"
    env._flow_config_default_compiler = None

    try:
        os.environ["DEV_CXX"] = "compiler-123"
        env._flow_config_default_compiler = {env.platform: "compiler-456"}

        assert env.default_compiler() == "compiler-123"

        del os.environ["DEV_CXX"]
        assert env.default_compiler() == "compiler-456"

        env._flow_config_default_compiler = None
        assert env.default_compiler() == "?"

    finally:
        env.platform = saved_platform
        env._flow_config_default_compiler = saved_compilers


def _print(*args: str, use_color: bool = True, secrets: List[str], raw: bool):
    with Capture() as capture:
        env.Printer.print_cmd(*args, use_color=use_color, secrets=secrets, raw=raw)

    return capture.stderr


PrinterTestTuple = collections.namedtuple(
    "PrinterTestTuple", ["use_color", "secrets", "raw", "expected"]
)

PRINTER_TEST: List[PrinterTestTuple] = [
    PrinterTestTuple(
        use_color=True,
        secrets=[],
        raw=False,
        expected="\x1b[33mcommand\x1b[m arg \x1b[2;37m--arg=123secret123\x1b[m "
        "\x1b[2;37m-secret1\x1b[m \x1b[2;34m'with space'\x1b[m\n",
    ),
    PrinterTestTuple(
        use_color=False,
        secrets=[],
        raw=False,
        expected="command arg --arg=123secret123 -secret1 'with space'\n",
    ),
    PrinterTestTuple(
        use_color=True,
        secrets=[],
        raw=True,
        expected="\x1b[33mcommand\x1b[m arg \x1b[2;37m--arg=123secret123\x1b[m "
        "\x1b[2;37m-secret1\x1b[m with space\n",
    ),
    PrinterTestTuple(
        use_color=False,
        secrets=[],
        raw=True,
        expected="command arg --arg=123secret123 -secret1 with space\n",
    ),
    PrinterTestTuple(
        use_color=False,
        secrets=["23secret1", "with space"],
        raw=False,
        expected="command arg '--arg=1???????????????23' -secret1 '???????????????'\n",
    ),
]


@pytest.mark.parametrize("use_color,secrets,raw,expected", PRINTER_TEST)
def test_printer(use_color, secrets, raw, expected):
    cmd = ("command", "arg", "--arg=123secret123", "-secret1", "with space")

    assert _print(*cmd, use_color=use_color, secrets=secrets, raw=raw) == expected
