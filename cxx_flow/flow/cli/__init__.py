# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import argparse
import os
import sys
from typing import List, cast

from cxx_flow import __version__, api
from cxx_flow.flow.cli import cmds
from cxx_flow.flow.steps import clean_aliases, load_steps


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


def __main():
    _change_dir()

    flow_cfg = api.env.FlowConfig()
    valid_steps = load_steps(flow_cfg)
    clean_aliases(flow_cfg, valid_steps)

    root = argparse.ArgumentParser(
        prog="cxx-flow", description="C++ project maintenance, automated"
    )
    root.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s version {__version__}"
    )
    root.add_argument(
        "-C",
        dest="cd",
        metavar="dir",
        nargs="?",
        help="runs as if cxx-flow was started in <dir> instead of the current working directory",
    )

    shortcut_configs = cmds.BuiltinEntry.visit_all(root, flow_cfg)
    args = root.parse_args()

    args_kwargs = dict(args._get_kwargs())
    for key in shortcut_configs:
        try:
            if not args_kwargs[key]:
                continue
            cast(List[List[str]], args.configs).append(shortcut_configs[key])
            break
        except KeyError:
            continue

    sys.exit(cmds.BuiltinEntry.run_entry(args, flow_cfg))


def main():
    try:
        __main()
    except KeyboardInterrupt:
        sys.exit(1)
