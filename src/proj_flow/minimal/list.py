# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.list** implements ``./flow list`` command.
"""

import os
import re
import sys
from typing import Annotated, Dict, Iterable, List, Set, cast

from proj_flow import cli
from proj_flow.api import arg, env, step
from proj_flow.base import matrix

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes
else:
    import termios


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
        builtin_entries = list(sorted(_walk_menu(menu)))
        if not pipe and len(builtin_entries) > 0:
            print("Builtin commands")
            print("----------------")

        for entry_name, entry_doc in builtin_entries:
            if pipe:
                print(entry_name)
                continue

            name = f"{bold}{entry_name}{reset}"
            if entry_doc:
                print(f"- {name}:", end=" ")
                _write_console_para(
                    " ".join(para.split("\n")) for para in entry_doc.split("\n\n")
                )
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
            print(f"- {name}:", end=" ")
            _write_console_para([", ".join(run_alias.steps)])

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
            _write_console_para(
                [
                    f"*step can only be run by explicitly calling through {bold}run{reset}."
                ]
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
                    print(f"- {name}:", end=" ")
                    _write_console_para([value])
                else:
                    print(f"- {name}")

        printed_something = True

    if not printed_something and not pipe:
        print(f"Use {bold}--help{reset} to see, which listings are available")


def _iterate_levels(menu: cli.argument.Command, prefix: str):
    yield [(f"{prefix}{cmd.name}", cmd.doc) for cmd in menu.children]
    for cmd in menu.children:
        child_prefix = f"{prefix}{cmd.name} "
        for layer in _iterate_levels(cmd, child_prefix):
            yield layer


def _walk_menu(menu: cli.argument.Command):
    root = menu
    while root.parent is not None:
        root = root.parent

    items: list[tuple[str, str]] = []
    for layer in _iterate_levels(root, ""):
        items.extend(layer)

    return items


def _cursor_pos():
    if sys.platform == "win32":
        old_stdin_mode = ctypes.wintypes.DWORD()
        old_stdout_mode = ctypes.wintypes.DWORD()
        kernel32 = ctypes.windll.kernel32
        kernel32.GetConsoleMode(
            kernel32.GetStdHandle(-10), ctypes.byref(old_stdin_mode)
        )
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), 0)
        kernel32.GetConsoleMode(
            kernel32.GetStdHandle(-11), ctypes.byref(old_stdout_mode)
        )
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    else:
        old_stdin_mode = termios.tcgetattr(sys.stdin)
        _ = termios.tcgetattr(sys.stdin)
        _[3] = _[3] & ~(termios.ECHO | termios.ICANON)
        termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, _)
    try:
        _ = ""
        sys.stdout.write("\x1b[6n")
        sys.stdout.flush()
        while not (_ := _ + sys.stdin.read(1)).endswith("R"):
            pass
        res = re.match(r".*\[(?P<y>\d*);(?P<x>\d*)R", _)
    finally:
        if sys.platform == "win32":
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), old_stdin_mode)
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), old_stdout_mode)
        else:
            termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, old_stdin_mode)
    if res:
        return (int(res.group("x")), int(res.group("y")))
    return (1, 1)


def _write_console_para(text: Iterable[str]):
    term_width = os.get_terminal_size().columns
    margin = min(_cursor_pos()[0], term_width // 2) - 1
    width = term_width - 1
    pos = margin
    for para in text:
        for word in para.split():
            if not word:
                continue
            word_len = len(word)
            next_pos = pos + word_len + 1

            if next_pos >= width:
                orig = pos
                if orig == margin:
                    pos = margin - word_len
                    print(word, end="")

                print()
                print(" " * margin, end="")

                if orig != margin:
                    pos = margin
                    print(word, end=" ")
            else:
                print(word, end=" ")

            pos += word_len + 1

            continue
            if (word_len + 1) > term_width:
                first_word = pos == margin
                if first_word:
                    print(word, end="")

                print(f"\n{' ' * margin}", end="")
                pos = margin

                if not first_word:
                    print(word, "", end="")
                    pos += word_len + 1
                continue

            print(word, "", end="")
            pos += word_len + 1
        print()


def _load_flow_data(rt: env.Runtime):
    paths = [os.path.join(".flow", "matrix.yml")]
    m, keys = matrix.load_matrix(*paths)

    if rt.no_coverage:
        for conf in m:
            if "coverage" in conf:
                del conf["coverage"]

    return m, keys
