# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.cli.finder** extends the :py:class:`argcomplete.finders.CompletionFinder`
to be able to see proper :class:`api.env.FlowConfig`, when completed invocation
contains ``-C`` argument.
"""

import os
import shlex
from pathlib import Path
from typing import List

from argcomplete import finders


def split_line(cli_text: str):
    """
    Split the command line being completed into arguments. If the last
    argument is still being typed and directly follows ``-C``, both the
    ``-C`` and the unfinished directory are dropped.

    :param cli_text: command line up to the cursor
    :returns: list of the arguments
    """
    last_is_finished = len(cli_text) > len(cli_text.rstrip())
    split = shlex.shlex(cli_text, posix=True)
    split.whitespace_split = True
    args = list(split)
    if not last_is_finished and len(args) > 2 and args[-2] == "-C":
        args = args[:-2]

    return args


def find_dash_see(args: List[str]):
    """
    Find the value of the last ``-C`` argument. A ``-C`` in the last position,
    with no value after it, is ignored.

    :param args: arguments of the command line, e.g. from :func:`split_line`
    :returns: index of the argument following the last ``-C``, or ``-1``, if
        there is no such argument
    """
    pos = -1
    max_pos = len(args)
    if max_pos:
        max_pos -= 1
    for index in range(max_pos):
        if args[index] == "-C":
            pos = index + 1

    return pos


class CompletionFinder(finders.CompletionFinder):
    """
    Completion finder, which can also tell, which project directory the
    completed command line points to with ``-C``.
    """

    def active(self):
        """
        Check, if the program was called by the shell to complete a command
        line.

        :returns: ``True``, if ``$_ARGCOMPLETE`` is set
        """
        return "_ARGCOMPLETE" in os.environ

    def find_project(self):
        """
        Find the project directory of the completed command line, based on
        ``$COMP_LINE`` and ``$COMP_POINT``.

        :returns: directory given with the last ``-C`` argument; current
            directory, if there is none or the completion is not active
        """
        if not self.active():
            return Path()

        comp_line = os.environ["COMP_LINE"]
        comp_point = int(os.environ["COMP_POINT"])
        args = split_line(comp_line[:comp_point])
        pos = find_dash_see(args)

        if pos < 0:
            return Path()

        return Path(args[pos])


autocomplete = CompletionFinder()
