# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.api.arg** is used by various commands to declare CLI arguments.
"""

import argparse
import inspect
import typing
from dataclasses import dataclass, field


@dataclass
class Argument:
    help: str = ""
    pos: bool = False
    names: typing.List[str] = field(default_factory=list)
    nargs: typing.Union[str, int, None] = None
    opt: typing.Optional[bool] = None
    meta: typing.Optional[str] = None
    action: typing.Union[str, argparse.Action, None] = None
    default: typing.Optional[typing.Any] = None
    choices: typing.Optional[typing.List[str]] = None
    completer: typing.Optional[callable] = None


class FlagArgument(Argument):
    def __init__(self, help: str = "", names: typing.List[str] = []):
        super().__init__(
            help=help, names=names, opt=True, action="store_true", default=False
        )


@dataclass
class _Command:
    name: str
    entry: typing.Optional[callable]
    doc: typing.Optional[str]
    subs: typing.Dict[str, "_Command"]

    def add(self, names: typing.List[str], entry: callable, doc: typing.Optional[str]):
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


_known_subcommand: typing.List[callable] = []
_known_commands = _Command("", None, None, {})


def flow_subcommand(entry: callable):
    global _known_subcommand
    _known_subcommand.append(entry)
    return entry


def get_subcommands():
    global _known_subcommand
    return _known_subcommand


_autodoc = {
    "cxx_flow.flow.configs.Configs": "Holds all current configurations.",
    "cxx_flow.api.env.Runtime": "Means to run tools and print messages, while respecting ``--dry-run``, ``--silent`` and ``--verbose``.",
}


def _type_name(t) -> str:
    if t == type(None):
        return "None"

    if type(t) == type:
        return t.__name__

    origin = typing.get_origin(t)

    if origin is typing.Union:
        seen: typing.Set[str] = set()
        names: typing.List[str] = []
        for arg in typing.get_args(t):
            for name in _union_args(arg):
                if name in seen:
                    continue
                names.append(name)
        return "|".join(names)

    if origin in [list, type, dict]:
        args = typing.get_args(t)
        arg_list = ", ".join(_type_name(arg) for arg in args)
        return f"{origin.__name__}[{arg_list}]"

    args = typing.get_args(t)
    arg_list = ", ".join(_type_name(arg) for arg in args)
    if arg_list:
        return f"{origin.__name__}[{arg_list}]"

    return typing.cast(str, origin.__name__)

def _union_args(t) -> typing.Generator[str, None, None]:
    origin = typing.get_origin(t)

    if origin is typing.Union:
        args = typing.get_args(t)
        for arg in args:
            for candidate in _union_args(arg):
                yield candidate
        return

    yield _type_name(t)
    

def command(*name: str):
    def wrap(entry: callable):
        global _known_commands
        _known_commands.add(list(name), entry, entry.__doc__)

        doc = inspect.getdoc(entry) or ""
        if doc:
            doc += "\n\n"

        signature = inspect.signature(entry)

        for param_name, param in signature.parameters.items():
            annotation = param.annotation

            if type(annotation) == type:
                full_name = f"{annotation.__module__}.{annotation.__name__}"
                help = _autodoc.get(full_name, "")
                doc += f":param {annotation.__name__} {param_name}: {help}\n"
                continue

            if typing.get_origin(annotation) is not typing.Annotated:
                continue

            anno_args = typing.get_args(annotation)
            if len(anno_args) == 0:
                continue
            
            origin = anno_args[0]

            help = ""
            for arg in anno_args[1:]:
                if isinstance(arg, Argument):
                    help = arg.help
                    if help:
                        break

            doc += f":param {_type_name(origin)} {param_name}: {help}\n"

        entry.__doc__ = doc

        return entry

    return wrap


def get_commands():
    return _known_commands
