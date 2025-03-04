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
from typing import List, Optional

from proj_flow.api.env import Runtime


@dataclass
class Statement:
    rule: "Rule"
    outputs: List[str]
    inputs: List[str]
    implicit_deps: List[str] = field(default_factory=list)

    def run(self, rt: Runtime):
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

        dep_mtime = 0.0
        for deps in [self.inputs, self.implicit_deps]:
            for dep in deps:
                try:
                    mtime = os.path.getmtime(dep)
                    dep_mtime = max(dep_mtime, mtime)
                except FileNotFoundError:
                    pass
        return dep_mtime > out_mtime


class Rule(ABC):
    @abstractmethod
    def command(self, statement: Statement) -> List[str]: ...

    def run(self, _statement: Statement, _rt: Runtime):
        return 1

    @classmethod
    def statement(
        cls,
        outputs: List[str],
        inputs: List[str],
        implicit_deps: Optional[List[str]] = None,
    ):
        return Statement(cls(), outputs, inputs, implicit_deps or [])


@dataclass(init=False)
class Makefile:
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

        Makefile._unlink_missing(unsorted)
        self.statements = Makefile._sort(unsorted)

    @staticmethod
    def _unlink_missing(unsorted: List["Makefile.Sorted"]):
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

    @staticmethod
    def _sort(unsorted: List["Makefile.Sorted"]):
        result: List[Statement] = []

        while len(unsorted):
            next_step_layer = [st for st in unsorted if len(st.deps) == 0]
            unsorted = [st for st in unsorted if len(st.deps) > 0]

            result.extend(st.ref for st in next_step_layer)
            for st in next_step_layer:
                for output in st.outputs:
                    for left in unsorted:
                        if output in left.deps:
                            left.deps.remove(output)

        return result

    def run(self, rt: Runtime):
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
