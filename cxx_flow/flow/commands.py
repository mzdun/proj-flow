# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import argparse
import inspect
import typing
from dataclasses import dataclass
from types import ModuleType
from typing import Annotated, Any, Dict, List, Optional, Tuple, Union, cast

from .. import commands
from .arg import Argument
from .config import Configs, FlowConfig, Runtime, default_compiler, platform


@dataclass
class SpecialArg:
    name: str
    ctor: callable


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

    def run(self, args: argparse.Namespace, cfg: FlowConfig):
        kwargs = {}
        for arg in self.args:
            kwargs[arg.name] = getattr(args, arg.name, None)

        for additional in self.additional:
            ctor = additional.ctor
            arg = ctor(args)
            kwargs[additional.name] = arg
            if ctor == Runtime:
                rt = cast(Runtime, arg)
                rt.steps = cfg.steps
                rt.aliases = cfg.aliases
                rt._cfg = cfg._cfg

        result = self.entry(**kwargs)
        return 0 if result is None else result

    @staticmethod
    def run_entry(args: argparse.Namespace, cfg: FlowConfig):
        builtin_entries = {entry.name for entry in command_list}
        aliases = cfg.aliases

        if args.command in builtin_entries:
            command = filter(
                lambda command: command.name == args.command, command_list
            ).__next__()
            return cast(BuiltinEntry, command).run(args, cfg)
        elif args.command in {alias.name for alias in aliases}:
            command = filter(
                lambda command: command.name == "run", command_list
            ).__next__()
            alias = filter(lambda alias: alias.name == args.command, aliases).__next__()
            args.steps.append(",".join(alias.steps))
            return cast(BuiltinEntry, command).run(args, cfg)

        print("known commands:")
        for command in command_list:
            print(f"   {command.name}: {command.doc}")
        for alias in aliases:
            print(f"   {alias.name}: {alias.doc}")
        return 1

    @staticmethod
    def visit_all(
        parser: argparse.ArgumentParser, cfg: FlowConfig
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
    def build_shortcuts(cfg: FlowConfig) -> Dict[str, List[str]]:
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
            os_prefix = f"os={platform}"
            compiler_prefix = f"compiler={default_compiler()}"

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

        parser.add_argument(
            "--silent",
            action="store_true",
            required=False,
            help="removes most of the output",
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
                f'if "os" is missing, it will default to additional "-D os={platform}"',
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


def _shortcut_value(value) -> str:
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    return str(value)


def _extract_arg(name: str, arg: Any):
    for ctor in [Configs, Runtime]:
        if arg is ctor:
            return SpecialArg(name, ctor)

    anno_type = typing.get_origin(arg)
    if anno_type is not Annotated:
        return None

    arg_dict = getattr(arg, "__dict__", {})
    origin = arg_dict.get("__origin__", None)
    (metadata,) = arg_dict.get("__metadata__", None)

    if origin is None or not isinstance(metadata, Argument):
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
            if additional.ctor == Runtime:
                has_rt = True
                break

        if not has_rt:
            continue

        return BuiltinEntry(modname, doc, entry, entry_args, special_args)


def _get_entries():
    submodules = inspect.getmembers(commands, inspect.ismodule)
    all_entries = map(lambda tup: _get_entry(*tup), submodules)
    valid_entries = filter(lambda entry: entry is not None, all_entries)
    return list(valid_entries)


command_list = _get_entries()
