# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.list** implements ``./flow list`` command.
"""

import os
from typing import Annotated, Dict, List, Set, cast

from proj_flow import cli
from proj_flow.api import arg, env, step
from proj_flow.base import matrix


@arg.command("list")
def main(
    builtin: Annotated[bool, arg.FlagArgument(help="Show all builtin commands")],
    alias: Annotated[bool, arg.FlagArgument(help="Show all alias commands")],
    steps: Annotated[bool, arg.FlagArgument(help="Show all run steps")],
    configs: Annotated[bool, arg.FlagArgument(help="Show all known matrix keys")],
    all: Annotated[
        bool, arg.FlagArgument(help="Show builtins, aliases, steps and configs")
    ],
    pipe: Annotated[bool, arg.FlagArgument(help="Do not show additional information")],
    rt: env.Runtime,
    menu: cli.argument.Command,
):
    """List all the commands and/or steps for proj-flow"""

    printed_something = False
    bold = "\033[96m" if rt.use_color else ""
    reset = "\033[0m" if rt.use_color else ""

    if all:
        builtin = True
        alias = True
        steps = True
        configs = True

    if builtin:
        root = menu
        while root.parent is not None:
            root = root.parent
        builtin_entries = list(sorted((cmd.name, cmd.doc) for cmd in root.children))
        if not pipe and len(builtin_entries) > 0:
            print("Builtin commands")
            print("----------------")

        for entry_name, entry_doc in builtin_entries:
            if pipe:
                print(entry_name)
                continue

            name = f"{bold}{entry_name}{reset}"
            if entry_doc:
                print(f"- {name}: {entry_doc}")
            else:
                print(f"- {name}")

        printed_something = True

    if alias:
        aliases = rt.aliases

        if not pipe and len(aliases) > 0:
            if printed_something:
                print()

            print("Known aliases")
            print("-------------")

        for run_alias in aliases:
            if pipe:
                print(run_alias.name)
                continue

            name = f"{bold}{run_alias.name}{reset}"
            print(f"- {name}: {', '.join(run_alias.steps)}")

        printed_something = True

    if steps:
        rt_steps = cast(List[step.Step], rt.steps)

        if not pipe and len(rt_steps) > 0:
            if printed_something:
                print()

            print("Run steps")
            print("---------")

        some_unused = False
        aliased_steps = set(matrix.flatten([alias.steps for alias in rt.aliases]))

        for rt_step in rt_steps:
            if pipe:
                print(rt_step.name)
                continue

            step_used = rt_step.name in aliased_steps
            if not step_used:
                some_unused = True

            name = f"{bold}{rt_step.name}{reset}"
            if step_used:
                print(f"- {name}")
            else:
                print(f"- {name}*")

        if some_unused:
            print(
                f"*step can only be run by explicitly calling through {bold}run{reset}."
            )

        printed_something = True

    if configs:
        m, keys = _load_flow_data(rt)
        if pipe:
            for key in keys:
                print(key)
        else:
            if len(keys) > 0:
                if printed_something:
                    print()

                print("Matrix keys")
                print("-----------")

            values: Dict[str, Set[str]] = {}

            for config in m:
                for key in keys:
                    value = config[key]
                    if isinstance(value, bool):
                        value = "ON" if value else "OFF"
                    else:
                        value = str(value)
                    try:
                        values[key].add(value)
                    except KeyError:
                        values[key] = {value}

            empty = set()
            for key in keys:
                value = ", ".join(values.get(key, empty))
                name = f"{bold}{key}{reset}"
                if value:
                    print(f"- {name}: {value}")
                else:
                    print(f"- {name}")

        printed_something = True

    if not printed_something and not pipe:
        print(f"Use {bold}--help{reset} to see, which listings are available")


def _load_flow_data(rt: env.Runtime):
    paths = [os.path.join(".flow", "matrix.yml")]
    m, keys = matrix.load_matrix(*paths)

    if rt.no_coverage:
        for conf in m:
            if "coverage" in conf:
                del conf["coverage"]

    return m, keys
