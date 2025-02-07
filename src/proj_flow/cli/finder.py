# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.cli.finder** extends the :py:class:`argcomplete.finders.CompletionFinder`
to be able to see proper :class:`api.env.FlowConfig`, when completed invocation
contains ``-C`` argument.
"""

import os
import shlex
from typing import List

from argcomplete import finders


def split_line(cli_text: str):
    last_is_finished = len(cli_text) > len(cli_text.rstrip())
    split = shlex.shlex(cli_text, posix=True)
    split.whitespace_split = True
    args = list(split)
    if not last_is_finished and len(args) > 2 and args[-2] == "-C":
        args = args[:-2]

    return args


def find_dash_see(args: List[str]):
    pos = -1
    max_pos = len(args)
    if max_pos:
        max_pos -= 1
    for index in range(max_pos):
        if args[index] == "-C":
            pos = index + 1

    return pos


class CompletionFinder(finders.CompletionFinder):
    def active(self):
        return "_ARGCOMPLETE" in os.environ

    def find_project(self):
        if not self.active():
            return "."

        comp_line = os.environ["COMP_LINE"]
        comp_point = int(os.environ["COMP_POINT"])
        args = split_line(comp_line[:comp_point])
        pos = find_dash_see(args)

        if pos < 0:
            return "."

        return args[pos]


autocomplete = CompletionFinder()
