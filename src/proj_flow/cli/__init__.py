# PYTHON_ARGCOMPLETE_OK

# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.cli** provides command-line entry for the *Project Flow*.
"""

import argparse
import os
import sys

from proj_flow.api import env
from proj_flow.cli import argument, finder
from proj_flow.flow import steps

__all__ = ["argument", "finder", "main"]


def main():
    """Entry point for ``proj-flow`` tool."""
    try:
        __main()
    except KeyboardInterrupt:
        sys.exit(1)


def _change_dir():
    root = argparse.ArgumentParser(
        prog="proj-flow",
        usage="proj-flow [-h] [--version] [-C [dir]] command ...",
        add_help=False,
    )
    root.add_argument("-C", dest="cd", nargs="?")

    args, _ = root.parse_known_args()
    if args.cd:
        os.chdir(args.cd)


def __main():
    _change_dir()

    flow_cfg = env.FlowConfig(root=finder.autocomplete.find_project())
    steps.clean_aliases(flow_cfg)

    parser = argument.build_argparser(flow_cfg)
    finder.autocomplete(parser)
    args = parser.parse_args()
    argument.expand_shortcuts(parser, args)

    raise SystemExit(parser.find_and_run_command(args))
