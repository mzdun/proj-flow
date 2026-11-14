# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.api.makefile** exposes simple makefile APIs, so extensions can
easily provide run steps with multiple scripts being called.
"""

import os
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from proj_flow.api.env import Runtime


@dataclass
class Statement:
    """
    Single build statement: a rule applied to its inputs and outputs. Create
    it with :meth:`Rule.statement`.
    """

    #: Rule producing the outputs.
    rule: "Rule"

    #: Files produced by the statement.
    outputs: List[str]

    #: Files the statement reads.
    inputs: List[str]

    #: Other files, which make the outputs out of date, when changed.
    implicit_deps: List[str] = field(default_factory=list)

    def run(self, rt: Runtime):
        """
        Run the statement, if any output is missing or older than the inputs
        and implicit dependencies. A rule with a :meth:`Rule.command` has the
        command run; otherwise :meth:`Rule.run` is called. With
        ``--dry-run``, the statement is reported without checking, if it is
        up to date.

        :param rt: runtime of the run
        :returns: ``False``, if the outputs were up to date; otherwise the
            exit code, ``0`` on success
        """
        command = self.rule.command(self)
        if len(command) == 0:
            return self._run_directly(rt)

        if rt.dry_run:
            rt.print(*command)
            return 0

        if not self._needed():
            return False

        return rt.cmd(*command)

    def _run_directly(self, rt: Runtime):
        if rt.dry_run:
            copy = Runtime(rt, rt)
            copy.dry_run = True
            return self.rule.run(self, copy)

        if not self._needed():
            return False

        return self.rule.run(self, rt)

    def _needed(self):
        out_mtime = None
        for out in self.outputs:
            try:
                mtime = os.path.getmtime(out)
                out_mtime = mtime if out_mtime is None else min(mtime, out_mtime)
            except FileNotFoundError:
                pass
        if out_mtime is None:
            return True

        dep_mtime = 0
        for deps in [self.inputs, self.implicit_deps]:
            for dep in deps:
                try:
                    mtime = os.path.getmtime(dep)
                    dep_mtime = max(dep_mtime, mtime)
                except FileNotFoundError:
                    pass
        return dep_mtime > out_mtime


class Rule(ABC):
    """
    Way of producing outputs from inputs, like a rule in a makefile.
    Implementations either return a command line from :meth:`command`, or
    return an empty list and do the work in :meth:`run`.
    """

    @abstractmethod
    def command(self, statement: Statement) -> List[str]:
        """
        Command line producing the outputs of the statement.

        :param statement: statement to build
        :returns: program with its arguments, or an empty list to have
            :meth:`run` called instead
        """
        ...

    def run(self, statement: Statement, rt: Runtime) -> int:
        """
        Produce the outputs of the statement directly, without running a
        command. Called only, if :meth:`command` returns an empty list; with
        ``--dry-run``, ``rt`` has ``dry_run`` set and the method is expected
        to only report, what it would do. The default implementation fails.

        :param statement: statement to build
        :param rt: runtime of the run
        :returns: exit code, ``0`` on success
        """
        return 1

    @classmethod
    def statement(
        cls, outputs: List[str], inputs: List[str], implicit_deps: List[str] = []
    ):
        """
        Create a statement for this rule; the rule class is instantiated
        without arguments.

        :param outputs: files produced by the statement
        :param inputs: files the statement reads
        :param implicit_deps: other files, which make the outputs out of date,
            when changed
        :returns: the new statement
        """
        return Statement(cls(), outputs, inputs, implicit_deps)


@dataclass(init=False)
class Makefile:
    """
    List of statements, sorted so each one runs after the statements
    producing its inputs. Inputs, which no statement produces, are expected to
    already exist.

    :param statements: statements to sort
    """

    statements: List[Statement]

    @dataclass
    class Sorted:
        outputs: List[str]
        deps: List[str]
        ref: Statement

    def __init__(self, statements: List[Statement]):
        unsorted = [
            Makefile.Sorted(
                outputs=[*st.outputs], deps=[*st.inputs, *st.implicit_deps], ref=st
            )
            for st in statements
        ]
        sorted: List[Statement] = []

        for st in unsorted:
            copy = [*st.deps]
            for dep in copy:
                found = False
                for node in unsorted:
                    if dep in node.outputs:
                        found = True
                        break
                if not found:
                    st.deps.remove(dep)

        while len(unsorted):
            next = [st for st in unsorted if len(st.deps) == 0]
            unsorted = [st for st in unsorted if len(st.deps) > 0]

            sorted.extend(st.ref for st in next)
            for st in next:
                for output in st.outputs:
                    for left in unsorted:
                        if output in left.deps:
                            left.deps.remove(output)

        self.statements = sorted

    def run(self, rt: Runtime):
        """
        Run the statements in order, stopping at the first failure. Prints
        "Nothing to do", if all outputs were up to date.

        :param rt: runtime of the run
        :returns: exit code of the first failing statement, or ``0``
        """
        counter = 0
        for statement in self.statements:
            result = statement.run(rt)
            if isinstance(result, bool):
                if not result:
                    counter += 1
            if result:
                return result
        if counter == len(self.statements):
            print("-- Nothing to do", file=sys.stderr)
        return 0
