# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)


import argparse
from typing import Annotated

from proj_flow.api import arg, env
from proj_flow.cli import argument

from ..capture import Capture
from ..load_flow_cfg import flow_cfg  # noqa: F401 pylint: disable=unused-import


@arg.command("subject")
def subject():
    "The subject command"


@arg.command("subject", "action")
def subject_action(_rt: env.Runtime, _arg: Annotated[str, arg.FlagArgument()]):
    "The action on subject"


def _args(**kwargs):
    return argparse.Namespace(**kwargs)


# pylint: disable-next=redefined-outer-name
def test_expand_shortcuts(flow_cfg):  # noqa: F811
    parser = argument.build_argparser(flow_cfg)

    args = _args(configs=[], tested=True, unused=False)
    argument.expand_shortcuts(parser, args)

    assert args.configs == ["os=test-os", "compiler=test-compiler", "a=b", "c=d"]


class RuntimeAndArgs:
    def __init__(self, _rt: env.Runtime, _args: argparse.Namespace):
        pass

    def something(self):
        pass


# pylint: disable-next=redefined-outer-name
def test_additional_arguments(flow_cfg):  # noqa: F811
    args = _args()
    rt = env.Runtime.from_flow_cfg(flow_cfg)
    menu = argument._build_menu(arg.get_commands(), None)

    additional = argument.AdditionalArgument(name="arg", ctor=RuntimeAndArgs).create(
        rt, args, menu
    )
    assert isinstance(additional, RuntimeAndArgs)

    additional = argument.AdditionalArgument(name="arg", ctor=env.Runtime).create(
        rt, args, menu
    )
    assert isinstance(additional, env.Runtime)
    assert additional is rt

    additional = argument.AdditionalArgument(name="arg", ctor=argument.Command).create(
        rt, args, menu
    )
    assert isinstance(additional, argument.Command)
    assert additional is menu


NO_CMD_ERROR = (
    "usage: proj-flow [-h] [-v] [-C [dir]] command ...\n"
    "proj-flow: error: the command argument is required; known commands:\n"
    "\n"
    "  - parent: The parent command\n"
    "  - subject: The subject command\n"
    "  - bootstrap: Finish bootstrapping on behalf of flow.py\n"
    "  - init: Initialize new project\n"
    "  - list: List all the commands and/or steps for proj-flow\n"
    "  - run: Run automation steps for current project\n"
    "  - system: Produce system information for CI pipelines\n"
    # "  - github: Interact with GitHub workflows and releases\n"
    '  - alias: Shortcut for "run -s Default,PropA,PropB"\n'
)


# pylint: disable-next=redefined-outer-name
def test_no_result(flow_cfg):  # noqa: F811
    parser = argument.build_argparser(flow_cfg)

    with Capture() as capture:
        try:
            parser.find_and_run_command(_args(command="no-such", verbose=True))
        except SystemExit:
            pass

    assert (
        capture.stdout
        == "-- Command: adding `parent` from `test_proj_flow.api.test_arg.parent(...)`\n"
        "-- Command: adding `parent child-1` from `test_proj_flow.api.test_arg.cmd(...)`\n"
        "-- Command: adding `parent child-2` from `test_proj_flow.api.test_arg.cmd2(...)`\n"
        "-- Command: adding `subject` from `test_proj_flow.cli.test_argument.subject(...)`\n"
        "-- Command: adding `subject action` from `test_proj_flow.cli.test_argument.subject_action(...)`\n"
        "-- Command: adding `bootstrap` from `proj_flow.minimal.bootstrap.main(...)`\n"
        "-- Command: adding `init` from `proj_flow.minimal.init.main(...)`\n"
        "-- Command: adding `list` from `proj_flow.minimal.list_cmd.main(...)`\n"
        "-- Command: adding `run` from `proj_flow.minimal.run.main(...)`\n"
        "-- Command: adding `system` from `proj_flow.minimal.system.main(...)`\n"
        # "-- Command: adding `github` from `proj_flow.ext.github.cli.github(...)`\n"
        # "-- Command: adding `github matrix` from `proj_flow.ext.github.cli.matrix(...)`\n"
        # "-- Command: adding `github release` from `proj_flow.ext.github.cli.release_cmd(...)`\n"
        # "-- Command: adding `github publish` from `proj_flow.ext.github.cli.publish_cmd(...)`\n"
        '-- Step: adding "Default" from `test_proj_flow.api.test_step.DefaultStep`\n'
        '-- Step: adding "PropA" from `test_proj_flow.api.test_step.PropStep1`\n'
        '-- Step: adding "PropB" from `test_proj_flow.api.test_step.PropStep2`\n'
        '-- Step: adding "Serial" from `test_proj_flow.api.test_step.SerialStep`\n'
        '-- Step: adding "Default" from `test_proj_flow.api.test_step.DefaultStep`\n'
    )
    assert capture.stderr == NO_CMD_ERROR


# pylint: disable-next=redefined-outer-name
def test_sub_parser(flow_cfg):  # noqa: F811
    parser = argument.build_argparser(flow_cfg)

    with Capture() as capture:
        try:
            parser.find_and_run_command(_args(command="subject"))
        except SystemExit:
            pass

    assert capture.stdout == ""
    assert capture.stderr == ""


# pylint: disable-next=redefined-outer-name
def test_sub_sub_parser_bad(flow_cfg):  # noqa: F811
    parser = argument.build_argparser(flow_cfg)

    with Capture() as capture:
        try:
            parser.find_and_run_command(_args(command="subject", command_0="inaction"))
        except SystemExit:
            pass

    assert capture.stdout == ""
    assert capture.stderr == "-- FATAL: cannot find inaction\n"


# pylint: disable-next=redefined-outer-name
def test_sub_sub_parser(flow_cfg):  # noqa: F811
    parser = argument.build_argparser(flow_cfg)

    with Capture() as capture:
        try:
            parser.find_and_run_command(
                _args(command="subject", command_0="action", _arg=False)
            )
        except SystemExit:
            pass

    assert capture.stdout == ""
    assert capture.stderr == ""


# pylint: disable-next=redefined-outer-name
def test_alias(flow_cfg):  # noqa: F811
    parser = argument.build_argparser(flow_cfg)

    args = _args(command="alias", cli_steps=[], configs=[], tested=True)

    with Capture() as capture:
        try:
            parser.find_and_run_command(args)
        except SystemExit:
            pass

    assert capture.stdout == ""
    assert (
        capture.stderr == "-- step 1/3: Default\n"
        "-- step 2/3: PropA\n"
        "-- step 3/3: Default\n"
    )
