# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.api.arg** is used by various commands to declare CLI arguments.
"""

import argparse
import inspect
import typing
from dataclasses import dataclass, field

from proj_flow.base import inspect as _inspect

T = typing.TypeVar("T")
LazyArgument = typing.Union[T, typing.Callable[[], T]]


def _eval(arg: LazyArgument[T]) -> T:
    if callable(arg):
        return typing.cast(T, arg())
    return arg


class _Completable(typing.Protocol):
    completer: _inspect.Function


@dataclass
class Argument:
    help: LazyArgument[str] = ""
    pos: bool = False
    names: LazyArgument[typing.List[str]] = field(default_factory=list)
    nargs: LazyArgument[typing.Union[str, int, None]] = None
    opt: LazyArgument[typing.Optional[bool]] = None
    meta: LazyArgument[typing.Optional[str]] = None
    action: LazyArgument[typing.Union[str, argparse.Action, None]] = None
    default: LazyArgument[typing.Optional[typing.Any]] = None
    choices: LazyArgument[typing.Optional[typing.List[str]]] = None
    completer: typing.Optional[_inspect.Function] = None

    def visit(self, parser: argparse.ArgumentParser, name: str):
        kwargs = {}

        self_help = _eval(self.help)
        self_names = _eval(self.names)
        self_nargs = _eval(self.nargs)
        self_opt = _eval(self.opt)
        self_meta = _eval(self.meta)
        self_action = _eval(self.action)
        self_default = _eval(self.default)
        self_choices = _eval(self.choices)

        if self_help is not None:
            kwargs["help"] = self_help
        if self_nargs is not None:
            kwargs["nargs"] = self_nargs
        if self_meta is not None:
            kwargs["metavar"] = self_meta
        if self_default is not None:
            kwargs["default"] = self_default
        if self_action is not None:
            kwargs["action"] = self_action
        if self_choices is not None:
            kwargs["choices"] = self_choices

        names = (
            [name] if self.pos else self_names if len(self_names) > 0 else [f"--{name}"]
        )

        if self.pos:
            kwargs["nargs"] = "?" if self_opt else 1
        else:
            kwargs["dest"] = name
            kwargs["required"] = not self_opt

        action = parser.add_argument(*names, **kwargs)
        if self.completer:
            typing.cast(_Completable, action).completer = self.completer

        return action


class FlagArgument(Argument):
    def __init__(self, help: str = "", names: typing.List[str] = []):
        super().__init__(
            help=help, names=names, opt=True, action="store_true", default=False
        )


@dataclass
class _Command:
    name: str
    entry: typing.Optional[_inspect.Function]
    doc: typing.Optional[str]
    subs: typing.Dict[str, "_Command"]

    def add(
        self,
        names: typing.List[str],
        entry: _inspect.Function,
        doc: typing.Optional[str],
    ):
        name = names[0]
        rest = names[1:]
        if len(rest):
            try:
                child = self.subs[name]
            except KeyError:
                child = _Command(name, None, None, {})
                self.subs[name] = child

            child.add(rest, entry, doc)
            return

        try:
            child = self.subs[name]
            child.entry = entry
            child.doc = doc
        except KeyError:
            self.subs[name] = _Command(name, entry, doc, {})


_known_commands = _Command("", None, None, {})
_autodoc = {
    "proj_flow.flow.configs.Configs": "Current configuration list.",
    "proj_flow.api.env.Runtime": "Tools and print messages, while respecting ``--dry-run``, ``--silent`` and ``--verbose``.",
    "proj_flow.cli.argument.Command": "The Command object attached to this @command function.",
}


def command(*name: str):
    def wrap(function: object):
        entry = typing.cast(_inspect.Function, function)
        global _known_commands
        orig_doc = inspect.getdoc(entry)
        _known_commands.add(list(name), entry, orig_doc)

        doc = orig_doc or ""
        if doc:
            doc += "\n\n"

        for arg in _inspect.signature(entry):
            help = ""
            for meta in arg.metadata:
                if isinstance(meta, Argument):
                    help = meta.help
                    if help:
                        break

            if not help:
                full_name = f"{arg.type.__module__}.{arg.type.__name__}"
                help = _autodoc.get(full_name, "")

            doc += f":param {_inspect.type_name(arg.type)} {arg.name}: {help}\n"

        entry.__doc__ = doc

        return entry

    return wrap


def get_commands():
    return _known_commands
