# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import argparse
from dataclasses import dataclass, field
from typing import Any, List, Optional, Union


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


class FlagArgument(Argument):
    def __init__(self, help: str = "", names: List[str] = []):
        super().__init__(help=help, names=names, action="store_true", default=False)


_known_subcommand: List[callable] = []


def flow_subcommand(entry: callable):
    global _known_subcommand
    _known_subcommand.append(entry)
    return entry


def get_subcommands():
    global _known_subcommand
    return _known_subcommand
