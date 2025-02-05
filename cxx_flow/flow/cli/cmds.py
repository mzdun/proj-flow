# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.flow.cli.cmds** provides command-line builders and runners,
supporting the functions defined in :mod:`cxx_flow.commands`.
"""

import argparse
import typing
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union, cast

from cxx_flow import __version__
from cxx_flow.api import arg, completers, env
from cxx_flow.base import inspect as _inspect
from cxx_flow.flow.configs import Configs


def build_argparser(flow_cfg: env.FlowConfig):
    parser = argparse.ArgumentParser(
        prog="cxx-flow",
        description="C++ project maintenance, automated",
        add_help=False,
    )
    parser.add_argument(
        "-h", "--help", action="help", help="Show this help message and exit"
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        default=argparse.SUPPRESS,
        version=f"%(prog)s version {__version__}",
        help="Show cxx-flow's version and exit",
    )
    parser.add_argument(
        "-C",
        metavar="dir",
        nargs="?",
        help="Run as if cxx-flow was started in <dir> instead of the current "
        "working directory. This directory must exist.",
    ).completer = completers.cd_completer  # type: ignore

    BuiltinEntry.visit_all(parser, flow_cfg)
    return parser


@dataclass
class SpecialArg:
    name: str
    ctor: callable  # type: ignore

    def create(self, rt: env.Runtime, args: argparse.Namespace):
        if self.ctor == env.Runtime:
            return rt
        return self.ctor(rt, args)


@dataclass
class EntryArg:
    name: str
    argument: arg.Argument

    def visit(self, parser: argparse.ArgumentParser):
        return self.argument.visit(parser, self.name)


@dataclass
class BuiltinEntry:
    name: str
    doc: str
    entry: callable  # type: ignore
    args: List[EntryArg]
    additional: List[SpecialArg]
    children: List["BuiltinEntry"] = field(default_factory=list)

    @staticmethod
    def run_entry(args: argparse.Namespace, cfg: env.FlowConfig):
        builtin_entries = {entry.name for entry in command_list}
        aliases = cfg.aliases

        rt = env.Runtime(args, cfg)

        if args.command in builtin_entries:
            command = first(lambda command: command.name == args.command, command_list)
            if command:
                return command.run(args, rt)
        elif args.command in {alias.name for alias in aliases}:
            command = first(lambda command: command.name == "run", command_list)
            alias = first(lambda alias: alias.name == args.command, aliases)
            if command and alias:
                args.cli_steps.append(",".join(alias.steps))
                return command.run(args, rt)

        print("known commands:")
        for command in command_list:
            print(f"   {command.name}: {command.doc}")
        for alias in aliases:
            print(f"   {alias.name}: {alias.doc}")
        return 1

    def run(self, args: argparse.Namespace, rt: env.Runtime, level=0):
        if level == 0 and rt.only_host:
            rt.only_host = self.name == "run"

        subcommand_name = None

        if len(self.children):
            subcommand_attribute = f"command_{level}"
            if hasattr(args, subcommand_attribute):
                subcommand_name = getattr(args, subcommand_attribute)

        if subcommand_name is not None:
            subcommand = first(
                lambda command: command.name == subcommand_name, self.children
            )
            if not subcommand:
                return 1
            return subcommand.run(args, rt, level=level + 1)

        kwargs = {}
        for arg in self.args:
            kwargs[arg.name] = getattr(args, arg.name, None)

        for additional in self.additional:
            arg = additional.create(rt, args)
            kwargs[additional.name] = arg

        result = self.entry(**kwargs)
        return 0 if result is None else result

    @staticmethod
    def visit_all(parser: argparse.ArgumentParser, cfg: env.FlowConfig):
        global command_list
        command_list = BuiltinEntry.build_menu(arg.get_commands().subs)
        shortcut_configs = BuiltinEntry.build_shortcuts(cfg)

        parser.flow = cfg  # type: ignore
        parser.shortcuts = shortcut_configs  # type: ignore

        subparsers = parser.add_subparsers(
            dest="command", metavar="{command}", help="Known command name, see below"
        )

        subparsers.parent = parser  # type: ignore

        run: Optional[BuiltinEntry] = None
        for entry in command_list:
            entry.visit(subparsers)
            if entry.name == "run":
                run = entry

        if run is not None and len(cfg.aliases) > 0:
            builtin_entries = {entry.name for entry in command_list}
            cfg.aliases = [
                alias for alias in cfg.aliases if alias.name not in builtin_entries
            ]
            for alias in cfg.aliases:
                run.visit(subparsers, alias=alias.name, doc=alias.doc)
        else:
            cfg.aliases = []

    def visit(
        self,
        subparsers,
        alias: Optional[str] = None,
        doc: Optional[str] = None,
        level=0,
    ):
        if not doc:
            doc = self.doc
        if not alias:
            alias = self.name

        parser: argparse.ArgumentParser = subparsers.add_parser(
            alias, help=doc.split("\n\n")[0], description=doc, add_help=False
        )

        parent = getattr(subparsers, "parent")
        parser.flow = getattr(parent, "flow")  # type: ignore
        parser.shortcuts = getattr(parent, "shortcuts")  # type: ignore

        assert parent.flow is not None
        assert parent.shortcuts is not None

        parser.add_argument(
            "-h",
            "--help",
            action="help",
            default=argparse.SUPPRESS,
            help="Show this help message and exit",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            required=False,
            help="Print steps and commands, do nothing",
        )

        verbosity = parser.add_mutually_exclusive_group()
        verbosity.add_argument(
            "--silent",
            action="store_true",
            required=False,
            help="Remove most of the output",
        )
        verbosity.add_argument(
            "--verbose",
            action="store_true",
            required=False,
            help="Add even more output",
        )

        has_config = False
        for additional in self.additional:
            if additional.ctor == Configs:
                has_config = True
                break

        if has_config:
            parser.add_argument(
                "-D",
                dest="configs",
                metavar="key=value",
                nargs="*",
                action="store",
                default=[],
                help="Run only builds on matching configs. The key is one of "
                'the keys into "matrix" object in .flow/matrix.yml definition '
                "and the value is one of the possible values for that key. In "
                "case of boolean flags, such as sanitizer, the true value is "
                'one of "true", "on", "yes", "1" and "with-<key>", '
                'i.e. "with-sanitizer" for sanitizer.'
                " "
                "If given key is never used, all values from .flow/matrix.yaml "
                "for that key are used. Otherwise, only values from command "
                "line are used.",
            ).completer = completers.matrix_completer  # type: ignore

            parser.add_argument(
                "--official",
                action="store_true",
                required=False,
                help="Cut matrix to release builds only",
            )

            if len(parser.shortcuts):  # type: ignore
                group = parser.add_mutually_exclusive_group()

                for shortcut_name in sorted(parser.shortcuts.keys()):  # type: ignore
                    config = parser.shortcuts[shortcut_name]  # type: ignore
                    group.add_argument(
                        f"--{shortcut_name}",
                        required=False,
                        action="store_true",
                        help=f'Shortcut for "-D {" ".join(config)}"',
                    )

        for arg in self.args:
            arg.visit(parser)

        if len(self.children):
            subparsers = parser.add_subparsers(
                dest=f"command_{level}",
                metavar="{command}",
                help="Known command name, see below",
            )
            subparsers.parent = parser  # type: ignore

            for entry in self.children:
                entry.visit(subparsers, level=level + 1)

    @staticmethod
    def build_shortcuts(cfg: env.FlowConfig) -> Dict[str, List[str]]:
        shortcut_configs: Dict[str, List[str]] = {}
        args: List[Tuple[str, List[str], bool, bool]] = []

        shortcuts = cfg.shortcuts
        for shortcut_name in sorted(shortcuts.keys()):
            has_os = False
            has_compiler = False
            shortcut = shortcuts[shortcut_name]
            config: List[str] = []
            for key in sorted(shortcut.keys()):
                has_os = has_os or key == "os"
                has_compiler = has_compiler or key == "os"
                value = shortcut[key]
                if isinstance(value, list):
                    for v in value:
                        config.append(f"{key}={_shortcut_value(v)}")
                else:
                    config.append(f"{key}={_shortcut_value(value)}")
            if len(config) > 0:
                args.append((shortcut_name, config, has_os, has_compiler))

        if len(args):
            os_prefix = f"os={env.platform}"
            compiler_prefix = f"compiler={env.default_compiler()}"

            for shortcut_name, config, has_os, has_compiler in args:
                if not has_compiler:
                    config.insert(0, compiler_prefix)
                if not has_os:
                    config.insert(0, os_prefix)
                shortcut_configs[shortcut_name] = config

        return shortcut_configs

    @staticmethod
    def build_menu(commands: Dict[str, arg._Command]):
        result: List[BuiltinEntry] = []
        for cmd in commands.values():
            name = cmd.name
            doc = cmd.doc or ""
            entry = cmd.entry or (lambda: 0)
            children = BuiltinEntry.build_menu(cmd.subs)

            args = _extract_args(entry)
            special_args = [entry for entry in args if isinstance(entry, SpecialArg)]
            entry_args = [entry for entry in args if isinstance(entry, EntryArg)]

            result.append(
                BuiltinEntry(
                    name=name,
                    doc=doc,
                    entry=entry,
                    args=entry_args,
                    additional=special_args,
                    children=children,
                )
            )

        return result


def _shortcut_value(value) -> str:
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    return str(value)


def _extract_arg(argument: _inspect.Argument):
    for ctor in [Configs, env.Runtime]:
        if argument.type is ctor:
            return SpecialArg(argument.name, ctor)

    metadata: Optional[arg.Argument] = first(
        lambda meta: isinstance(meta, arg.Argument), argument.metadata
    )

    if metadata is None or argument.type is None:
        return None

    optional = metadata.opt
    if optional is None:
        optional = typing.get_origin(argument.type) is Union and type(
            None
        ) in typing.get_args(argument.type)
    metadata.opt = optional

    return EntryArg(argument.name, metadata)


AnArg = Union[EntryArg, SpecialArg]


def _extract_args(entry: callable):  # type: ignore
    args_with_possible_nones = map(_extract_arg, _inspect.signature(entry))
    args = filter(lambda item: item is not None, args_with_possible_nones)
    return cast(List[AnArg], list(args))


T = typing.TypeVar("T")


def first(fltr: typing.Callable[[T], bool], items: typing.Iterable[T]) -> Optional[T]:
    try:
        return next(filter(fltr, items))
    except StopIteration:
        return None


command_list: List[BuiltinEntry] = []
