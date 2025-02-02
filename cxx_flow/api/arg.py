# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.api.arg** is used by various commands to declare CLI arguments.
"""

import argparse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class Argument:
    help: str = ""
    pos: bool = False
    names: List[str] = field(default_factory=list)
    nargs: Union[str, int, None] = None
    meta: Optional[str] = None
    action: Union[str, argparse.Action, None] = None
    default: Optional[Any] = None
    choices: Optional[List[str]] = None
    completer: Optional[callable] = None


class FlagArgument(Argument):
    def __init__(self, help: str = "", names: List[str] = []):
        super().__init__(help=help, names=names, action="store_true", default=False)


@dataclass
class _Command:
    name: str
    entry: Optional[callable]
    doc: Optional[str]
    subs: Dict[str, "_Command"]

    def add(self, names: List[str], entry: callable, doc: Optional[str]):
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


_known_subcommand: List[callable] = []
_known_commands = _Command("", None, None, {})


def flow_subcommand(entry: callable):
    global _known_subcommand
    _known_subcommand.append(entry)
    return entry


def get_subcommands():
    global _known_subcommand
    return _known_subcommand


def command(*name: str):
    def wrap(entry: callable):
        global _known_commands
        _known_commands.add(list(name), entry, entry.__doc__)

        return entry

    return wrap


def get_commands():
    return _known_commands
