# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import argparse
import typing

import pytest

from proj_flow.api import arg, env
from proj_flow.api.arg import Argument, FlagArgument, _Command, command
from proj_flow.cli.argument import Parser, build_argparser

from ..capture import Capture
from ..mocks import fs

arg._known_commands = _Command("", None, None, {})


@command("parent", "child-1")
def cmd():
    "A command"


@command("parent")
def parent(
    _items: list,
    _data: typing.Tuple[int, str, typing.Union[int, str]],
    _count: typing.Annotated[int, True],
):
    "The parent command"


def get_choices():
    return ["a", "b", "c", "d"]


@command("parent", "child-2")
def cmd2(
    _arg: typing.Annotated[
        typing.Optional[str], Argument(help="An argument", choices=get_choices)
    ],
    _flag: typing.Annotated[bool, FlagArgument(help="An argument")],
    _rt: env.Runtime,
):
    "Another command"


def test_docstrings():
    assert cmd.__doc__ == "A command"
    assert (
        cmd2.__doc__ == "Another command\n"
        "\n"
        ":param str | None _arg: An argument\n"
        ":param bool _flag: An argument\n"
        ":param Runtime _rt: Tools and print messages, while respecting ``--dry-run``, ``--silent`` and ``--verbose``.\n"
    )
    assert (
        parent.__doc__ == "The parent command\n\n"
        ":param list _items: \n"
        ":param tuple[int, str, int | str] _data: \n"
        ":param int _count: \n"
    )


def load_cfg(mocker):
    wrapper = fs({"./.flow/config.yaml": {}})
    mocker.patch("builtins.open", wraps=wrapper)
    return env.FlowConfig.load(root=".")


def get_help(parser: Parser, *args: str):
    with Capture() as capture:
        try:
            parser.parse_args([*args, "--help"])
        except SystemExit:
            pass
    return capture.stdout


TestTuple = typing.Tuple[typing.List[str], str]

COMMAND_TREE: typing.List[TestTuple] = [
    (
        [],
        """usage: proj-flow [-h] [-v] [-C [dir]] command ...

Project maintenance, automated

positional arguments:
  command        Known command name, see below
    parent       The parent command
    subject      The subject command
    bootstrap    Finish bootstrapping on behalf of flow.py
    init         Initialize new project
    list         List all the commands and/or steps for proj-flow
    run          Run automation steps for current project
    system       Produce system information for CI pipelines

options:
  -h, --help     Show this help message and exit
  -v, --version  Show proj-flow's version and exit
  -C [dir]       Run as if proj-flow was started in <dir> instead of the current working directory. This directory must exist.
""",
    ),
    (
        ["parent"],
        """usage: proj-flow parent [-h] [--dry-run] [--silent | --verbose] command ...

The parent command

positional arguments:
  command     Known command name, see below
    child-1   A command
    child-2   Another command

options:
  -h, --help  Show this help message and exit
  --dry-run   Print steps and commands, do nothing
  --silent    Remove most of the output
  --verbose   Add even more output
""",
    ),
    (
        ["parent", "child-1"],
        """usage: proj-flow parent child-1 [-h] [--dry-run] [--silent | --verbose]

A command

options:
  -h, --help  Show this help message and exit
  --dry-run   Print steps and commands, do nothing
  --silent    Remove most of the output
  --verbose   Add even more output
""",
    ),
    (
        ["parent", "child-2"],
        """usage: proj-flow parent child-2 [-h] [--dry-run] [--silent | --verbose] [--_arg {a,b,c,d}] [--_flag]

Another command

options:
  -h, --help        Show this help message and exit
  --dry-run         Print steps and commands, do nothing
  --silent          Remove most of the output
  --verbose         Add even more output
  --_arg {a,b,c,d}  An argument
  --_flag           An argument
""",
    ),
]


@pytest.mark.parametrize("cmds,expected", COMMAND_TREE)
def test_command_tree(cmds, expected, mocker):
    cfg = load_cfg(mocker)  # noqa: F841, pylint: disable=unused-variable
    parser = build_argparser(cfg)
    parser.formatter_class = argparse.RawTextHelpFormatter

    assert get_help(parser, *cmds) == expected
