# PYTHON_ARGCOMPLETE_OK

# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import argparse
import os
import sys
from typing import List, cast

from cxx_flow import __version__
from cxx_flow.flow.cli import cmds, finder
from cxx_flow.flow.steps import get_flow_config


def _change_dir():
    root = argparse.ArgumentParser(
        prog="cxx-flow",
        usage="cxx-flow [-h] [--version] [-C [dir]] {command} ...",
        add_help=False,
    )
    root.add_argument("-C", dest="cd", nargs="?")

    args, _ = root.parse_known_args()
    if args.cd:
        os.chdir(args.cd)


def _expand_shortcuts(parser: argparse.ArgumentParser, args: argparse.Namespace):
    args_kwargs = dict(args._get_kwargs())
    for key in parser.shortcuts:
        try:
            if not args_kwargs[key]:
                continue
            cast(List[List[str]], args.configs).append(parser.shortcuts[key])
            break
        except KeyError:
            continue


def __main():
    _change_dir()

    flow_cfg = get_flow_config(finder.autocomplete.find_project())
    parser = cmds.build_argparser(flow_cfg)

    finder.autocomplete(parser)
    args = parser.parse_args()
    _expand_shortcuts(parser, args)

    sys.exit(cmds.BuiltinEntry.run_entry(args, flow_cfg))


def main():
    try:
        __main()
    except KeyboardInterrupt:
        sys.exit(1)
