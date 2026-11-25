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
from typing import List, Optional, Set

from proj_flow.api.env import Runtime, StepFailed


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

    def run(self, rt: Runtime, rebuilt: Optional[Set[str]] = None) -> bool:
        """
        Run the statement, if any output is missing or older than any of the
        inputs and implicit dependencies. A rule with a :meth:`Rule.command`
        has the command run; otherwise :meth:`Rule.run` is called. With
        ``--dry-run``, the statement is only reported.

        :param rt: runtime of the run
        :param rebuilt: files, which are (or, with ``--dry-run``, would be)
            rebuilt earlier in this run; a statement depending on any of them
            is out of date regardless of the timestamps
        :returns: ``False``, if the outputs were up to date, ``True``, if the
            statement ran (or would, with ``--dry-run``)
        :raises StepFailed: the command or the rule has failed
        """
        if not self._needed(rebuilt or set()):
            return False

        command = self.rule.command(self)
        if len(command) == 0:
            if rt.dry_run:
                copy = Runtime(rt, rt)
                copy.dry_run = True
                self.rule.run(self, copy)
            else:
                self.rule.run(self, rt)
            return True

        if rt.dry_run:
            rt.print(*command)
        else:
            rt.cmd(*command)
        return True

    def _needed(self, rebuilt: Set[str]) -> bool:
        if any(dep in rebuilt for dep in [*self.inputs, *self.implicit_deps]):
            return True

        out_mtime: Optional[float] = None
        for out in self.outputs:
            try:
                mtime = os.path.getmtime(out)
            except FileNotFoundError:
                return True
            out_mtime = mtime if out_mtime is None else min(mtime, out_mtime)
        if out_mtime is None:
            return True

        for dep in [*self.inputs, *self.implicit_deps]:
            try:
                if os.path.getmtime(dep) > out_mtime:
                    return True
            except FileNotFoundError:
                return True
        return False


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

    def run(self, statement: Statement, rt: Runtime) -> None:
        """
        Produce the outputs of the statement directly, without running a
        command. Called only, if :meth:`command` returns an empty list; with
        ``--dry-run``, ``rt`` has ``dry_run`` set and the method is expected
        to only report, what it would do. The default implementation raises
        :py:exc:`NotImplementedError`.

        :param statement: statement to build
        :param rt: runtime of the run
        :raises StepFailed: the outputs could not be produced
        """
        raise NotImplementedError()

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


class CyclicDependencyError(Exception):
    """
    Statements of a :class:`Makefile` depend on each other's outputs, so they
    cannot be ordered.

    :param outputs: outputs of the statements, which could not be ordered
    """

    def __init__(self, outputs: List[str]):
        super().__init__(f"Cyclic dependency between: {', '.join(outputs)}")
        self.outputs = outputs


@dataclass(init=False)
class Makefile:
    """
    List of statements, sorted so each one runs after the statements
    producing its inputs. Inputs, which no statement produces, are expected to
    already exist.

    :param statements: statements to sort
    :raises CyclicDependencyError: some statements depend on each other's
        outputs
    """

    statements: List[Statement]

    @dataclass
    class Sorted:
        outputs: List[str]
        deps: List[str]
        ref: Statement

    def __init__(self, statements: List[Statement]):
        produced = {output for st in statements for output in st.outputs}
        pending = [
            Makefile.Sorted(
                outputs=[*st.outputs],
                deps=[
                    dep for dep in [*st.inputs, *st.implicit_deps] if dep in produced
                ],
                ref=st,
            )
            for st in statements
        ]
        ordered: List[Statement] = []

        while pending:
            ready = [st for st in pending if not st.deps]
            if not ready:
                raise CyclicDependencyError(
                    sorted({output for st in pending for output in st.outputs})
                )

            pending = [st for st in pending if st.deps]
            ordered.extend(st.ref for st in ready)

            done = {output for st in ready for output in st.outputs}
            for st in pending:
                st.deps = [dep for dep in st.deps if dep not in done]

        self.statements = ordered

    def run(self, rt: Runtime) -> None:
        """
        Run the statements in order, stopping at the first failure. Prints
        "Nothing to do", if all outputs were up to date.

        :param rt: runtime of the run
        :raises StepFailed: a statement has failed
        """
        rebuilt: Set[str] = set()
        ran = False
        for statement in self.statements:
            if statement.run(rt, rebuilt):
                ran = True
                rebuilt.update(statement.outputs)
        if not ran:
            print("-- Nothing to do", file=sys.stderr)
