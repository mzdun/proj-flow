# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import argparse
import inspect
import itertools
import typing
from dataclasses import dataclass, field
from types import ModuleType
from typing import Annotated, Any, Dict, List, Optional, Tuple, Union, cast

from cxx_flow import commands
from cxx_flow.api import arg, env
from cxx_flow.flow.configs import Configs


@dataclass
class SpecialArg:
    name: str
    ctor: callable

    def create(self, rt: env.Runtime, args: argparse.Namespace):
        if self.ctor == env.Runtime:
            return rt
        return self.ctor(rt, args)


@dataclass
class EntryArg:
    name: str
    opt: bool
    help: str
    pos: bool
    names: List[str]
    nargs: Union[str, int, None]
    meta: Optional[str]
    action: Union[str, argparse.Action, None]
    default: Optional[Any]
    choices: Optional[List[str]] = None

    def visit(self, parser: argparse.ArgumentParser):
        kwargs = {}
        if self.help is not None:
            kwargs["help"] = self.help
        if self.nargs is not None:
            kwargs["nargs"] = self.nargs
        if self.meta is not None:
            kwargs["metavar"] = self.meta
        if self.default is not None:
            kwargs["default"] = self.default
        if self.action is not None:
            kwargs["action"] = self.action
        if self.choices is not None:
            kwargs["choices"] = self.choices

        names = (
            [self.name]
            if self.pos
            else self.names if len(self.names) > 0 else [f"--{self.name}"]
        )

        if self.pos:
            kwargs["nargs"] = "?" if self.opt else 1
        else:
            kwargs["dest"] = self.name
            kwargs["required"] = not self.opt

        parser.add_argument(*names, **kwargs)


@dataclass
class BuiltinEntry:
    name: str
    doc: str
    entry: callable
    args: List[EntryArg]
    additional: List[SpecialArg]
    children: List["BuiltinEntry"] = field(default_factory=list)

    def run(self, args: argparse.Namespace, rt: env.Runtime, level=0):
        if level == 0 and rt.only_host:
            rt.only_host = self.name == "run"

        if len(self.children):
            subcommand_attribute = f"command_{level}"
            if hasattr(args, subcommand_attribute):
                subcommand_name = getattr(args, subcommand_attribute)
                subcommand = cast(
                    BuiltinEntry,
                    next(
                        filter(
                            lambda command: command.name == subcommand_name,
                            self.children,
                        )
                    ),
                )
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
    def run_entry(args: argparse.Namespace, cfg: env.FlowConfig):
        builtin_entries = {entry.name for entry in command_list}
        aliases = cfg.aliases

        rt = env.Runtime(args)
        rt.steps = cfg.steps
        rt.aliases = cfg.aliases
        rt._cfg = cfg._cfg

        if args.command in builtin_entries:
            command = next(
                filter(lambda command: command.name == args.command, command_list)
            )
            return cast(BuiltinEntry, command).run(args, rt)
        elif args.command in {alias.name for alias in aliases}:
            command = next(filter(lambda command: command.name == "run", command_list))
            alias = next(filter(lambda alias: alias.name == args.command, aliases))
            args.steps.append(alias.steps)
            return cast(BuiltinEntry, command).run(args, rt)

        print("known commands:")
        for command in command_list:
            print(f"   {command.name}: {command.doc}")
        for alias in aliases:
            print(f"   {alias.name}: {alias.doc}")
        return 1

    @staticmethod
    def visit_all(
        parser: argparse.ArgumentParser, cfg: env.FlowConfig
    ) -> Dict[str, List[str]]:
        shortcut_configs = BuiltinEntry.build_shortcuts(cfg)

        subparsers = parser.add_subparsers(
            dest="command", metavar="{command}", help="known command name, see below"
        )

        run: BuiltinEntry = None
        for entry in command_list:
            entry.visit(shortcut_configs, subparsers)
            if entry.name == "run":
                run = entry

        if run is not None and len(cfg.aliases) > 0:
            builtin_entries = {entry.name for entry in command_list}
            cfg.aliases = [
                alias for alias in cfg.aliases if alias.name not in builtin_entries
            ]
            for alias in cfg.aliases:
                run.visit(shortcut_configs, subparsers, alias=alias.name, doc=alias.doc)
        else:
            cfg.aliases = []

        return shortcut_configs

    @staticmethod
    def build_shortcuts(cfg: env.FlowConfig) -> Dict[str, List[str]]:
        shortcut_configs: Dict[str, List[str]] = {}
        args: List[Tuple[str, List[str]]] = []

        shortcuts = cfg.shortcuts
        for shortcut_name in sorted(shortcuts.keys()):
            shortcut = shortcuts[shortcut_name]
            config: List[str] = []
            for key in sorted(shortcut.keys()):
                value = shortcut[key]
                if isinstance(value, list):
                    for v in value:
                        config.append(f"{key}={_shortcut_value(v)}")
                else:
                    config.append(f"{key}={_shortcut_value(value)}")
            if len(config) > 0:
                args.append((shortcut_name, config))

        if len(args):
            os_prefix = f"os={env.platform}"
            compiler_prefix = f"compiler={env.default_compiler()}"

            for shortcut_name, config in args:
                config.insert(0, compiler_prefix)
                config.insert(0, os_prefix)
                shortcut_configs[shortcut_name] = config

        return shortcut_configs

    def visit(
        self,
        shortcut_configs: Dict[str, List[str]],
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
            alias, help=doc, description=doc
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            required=False,
            help="print steps and commands, do nothing",
        )

        verbosity = parser.add_mutually_exclusive_group()
        verbosity.add_argument(
            "--silent",
            action="store_true",
            required=False,
            help="removes most of the output",
        )
        verbosity.add_argument(
            "--verbose",
            action="store_true",
            required=False,
            help="adds more output",
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
                metavar="config",
                nargs="*",
                action="append",
                default=[],
                help="run only build matching the config; "
                "each filter is a name of a matrix axis followed by comma-separated values to take; "
                f'if "os" is missing, it will default to additional "-D os={env.platform}"',
            )

            parser.add_argument(
                "--official",
                action="store_true",
                required=False,
                help="cut matrix to minimal set of builds",
            )

            if len(shortcut_configs):
                group = parser.add_mutually_exclusive_group()

                for shortcut_name in sorted(shortcut_configs.keys()):
                    config = shortcut_configs[shortcut_name]
                    group.add_argument(
                        f"--{shortcut_name}",
                        required=False,
                        action="store_true",
                        help=f'shortcut for "-D {" ".join(config)}"',
                    )

        for arg in self.args:
            arg.visit(parser)

        if len(self.children):
            subparsers = parser.add_subparsers(
                dest=f"command_{level}",
                metavar="{command}",
                help="known command name, see below",
            )
            for entry in self.children:
                entry.visit(shortcut_configs, subparsers, level=level + 1)


def _shortcut_value(value) -> str:
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    return str(value)


def _extract_arg(name: str, argument: Any):
    for ctor in [Configs, env.Runtime]:
        if argument is ctor:
            return SpecialArg(name, ctor)

    anno_type = typing.get_origin(argument)
    if anno_type is not Annotated:
        return None

    arg_dict = getattr(argument, "__dict__", {})
    origin = arg_dict.get("__origin__", None)
    (metadata,) = arg_dict.get("__metadata__", None)

    if origin is None or not isinstance(metadata, arg.Argument):
        return None

    optional = typing.get_origin(origin) is Union and type(None) in typing.get_args(
        origin
    )
    return EntryArg(name, optional, **metadata.__dict__)


def _extract_args(entry: callable) -> List[Union[EntryArg, SpecialArg]]:
    entry_args = inspect.get_annotations(entry)
    nullable_args = (
        _extract_arg(name, entry_args[name]) for name in sorted(entry_args.keys())
    )
    args = filter(lambda item: item is not None, nullable_args)
    return list(args)


def _get_entry(modname: str, module: ModuleType):
    names = ["main", modname, f"command_{modname}"]
    for name, entry in inspect.getmembers(module):
        if not inspect.isfunction(entry) or name not in names:
            continue

        doc = inspect.getdoc(entry)
        args = _extract_args(entry)
        special_args = [entry for entry in args if isinstance(entry, SpecialArg)]
        entry_args = [entry for entry in args if isinstance(entry, EntryArg)]

        has_rt = False
        for additional in special_args:
            if additional.ctor == env.Runtime:
                has_rt = True
                break

        if not has_rt:
            continue

        return BuiltinEntry(modname, doc, entry, entry_args, special_args)


@dataclass
class SubEntry:
    command: str
    name: str
    doc: str
    entry: callable

    def expand(self):
        args = _extract_args(self.entry)
        special_args = [entry for entry in args if isinstance(entry, SpecialArg)]
        entry_args = [entry for entry in args if isinstance(entry, EntryArg)]

        has_rt = False
        for additional in special_args:
            if additional.ctor == env.Runtime:
                has_rt = True
                break

        if not has_rt:
            return None

        return BuiltinEntry(self.name, self.doc, self.entry, entry_args, special_args)


def _get_subentry(entry: callable):
    module = inspect.getmodule(entry)
    command = module.__name__.split(".")[2]
    name = entry.__name__
    doc = inspect.getdoc(entry)
    return SubEntry(command=command, name=name, doc=doc, entry=entry)


def _get_entries():
    submodules = inspect.getmembers(commands, inspect.ismodule)
    subcommands = {
        command: list(group)
        for command, group in itertools.groupby(
            map(_get_subentry, arg.get_subcommands()), lambda subentry: subentry.command
        )
    }
    all_entries = map(lambda tup: _get_entry(*tup), submodules)
    valid_entries = cast(
        List[BuiltinEntry], list(filter(lambda entry: entry is not None, all_entries))
    )

    for entry in valid_entries:
        if entry.name not in subcommands:
            continue
        children = subcommands[entry.name]
        all_children = map(lambda sub: sub.expand(), children)
        entry.children = cast(
            List[BuiltinEntry], list(filter(lambda sub: sub is not None, all_children))
        )

    return valid_entries


command_list = _get_entries()
