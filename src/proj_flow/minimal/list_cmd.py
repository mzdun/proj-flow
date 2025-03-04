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


class Lister:
    rt: env.Runtime
    pipe: bool
    printed_something: bool
    bold: str
    reset: str

    def __init__(self, rt: env.Runtime, pipe: bool):
        self.rt = rt
        self.pipe = pipe
        self.printed_something = False
        self.bold = "\033[96m" if rt.use_color else ""
        self.reset = "\033[0m" if rt.use_color else ""

    def _print_header(self, header: str, flag: bool):
        if self.pipe or not flag:
            return

        if self.printed_something:
            print()

        print(header)
        print("-" * len(header))
        self.printed_something = True

    def print_builtin(self, menu: cli.argument.Command):
        root = menu
        while root.parent is not None:
            root = root.parent

        builtin_entries = list(sorted((cmd.name, cmd.doc) for cmd in root.children))

        self._print_header("Builtin commands", len(builtin_entries) > 0)

        for entry_name, entry_doc in builtin_entries:
            self.printed_something = True
            if self.pipe:
                print(entry_name)
                continue

            name = f"{self.bold}{entry_name}{self.reset}"
            if entry_doc:
                print(f"- {name}: {entry_doc}")
            else:
                print(f"- {name}")

    def print_aliases(self):
        aliases = self.rt.aliases

        self._print_header("Known aliases", len(aliases) > 0)

        for run_alias in aliases:
            self.printed_something = True

            if self.pipe:
                print(run_alias.name)
                continue

            name = f"{self.bold}{run_alias.name}{self.reset}"
            print(f"- {name}: {', '.join(run_alias.steps)}")

    def print_steps(self):
        rt_steps = cast(List[step.Step], self.rt.steps)

        self._print_header("Run steps", len(rt_steps) > 0)

        some_unused = False
        aliased_steps = set(matrix.flatten([alias.steps for alias in self.rt.aliases]))

        for rt_step in rt_steps:
            self.printed_something = True
            if self.pipe:
                print(rt_step.name)
                continue

            step_used = rt_step.name in aliased_steps
            if not step_used:
                some_unused = True

            name = f"{self.bold}{rt_step.name}{self.reset}"
            if step_used:
                print(f"- {name}")
            else:
                print(f"- {name}*")

        if some_unused:
            print(
                f"*step can only be run by explicitly calling through {self.bold}run{self.reset}."
            )

    def print_configs(self):
        m, keys = _load_flow_data(self.rt)
        if self.pipe:
            for key in keys:
                self.printed_something = True
                print(key)
            return

        self._print_header("Matrix keys", len(keys) > 0)

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

        empty: Set[str] = set()
        for key in keys:
            self.printed_something = True
            value = ", ".join(values.get(key, empty))
            name = f"{self.bold}{key}{self.reset}"
            if value:
                print(f"- {name}: {value}")
            else:
                print(f"- {name}")

    def print(
        self,
        *,
        builtin: bool,
        alias: bool,
        steps: bool,
        configs: bool,
        menu: cli.argument.Command,
    ):
        if builtin:
            self.print_builtin(menu)

        if alias:
            self.print_aliases()

        if steps:
            self.print_steps()

        if configs:
            self.print_configs()

        if not self.printed_something and not self.pipe:
            print(
                f"Use {self.bold}--help{self.reset} to see, which listings are available"
            )


@arg.command("list")
def main(
    *,
    builtin: Annotated[bool, arg.FlagArgument(help="Show all builtin commands")],
    alias: Annotated[bool, arg.FlagArgument(help="Show all alias commands")],
    steps: Annotated[bool, arg.FlagArgument(help="Show all run steps")],
    configs: Annotated[bool, arg.FlagArgument(help="Show all known matrix keys")],
    all_flags: Annotated[
        bool,
        arg.FlagArgument(
            help="Show builtins, aliases, steps and configs", names=["--all"]
        ),
    ],
    pipe: Annotated[bool, arg.FlagArgument(help="Do not show additional information")],
    rt: env.Runtime,
    menu: cli.argument.Command,
):
    """List all the commands and/or steps for proj-flow"""

    if all_flags:
        builtin = True
        alias = True
        steps = True
        configs = True

    Lister(rt, pipe).print(
        builtin=builtin, alias=alias, steps=steps, configs=configs, menu=menu
    )


def _load_flow_data(rt: env.Runtime):
    paths = [os.path.join(".flow", "matrix.yml")]
    m, keys = matrix.load_matrix(*paths)

    if rt.no_coverage:
        for conf in m:
            if "coverage" in conf:
                del conf["coverage"]

    return m, keys
