# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from ..flow import matrix
from .config import Config, Runtime


class Step(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def runs_after(self) -> List[str]:
        return []

    @property
    def runs_before(self) -> List[str]:
        return []

    def platform_dependencies(self) -> List[str]:
        return []

    def is_active(self, config: Config, rt: Runtime) -> bool:
        return True

    def directories_to_remove(self, config: Config) -> List[str]:
        return []

    @abstractmethod
    def run(self, config: Config, rt: Runtime) -> int: ...


class SerialStep(Step):
    children: List[Step] = []

    @property
    def runs_after(self):
        return matrix.flatten([child.runs_after for child in self.children])

    def platform_dependencies(self) -> List[str]:
        return matrix.flatten(
            [child.platform_dependencies() for child in self.children]
        )

    def is_active(self, config: Config, rt: Runtime) -> bool:
        for child in self.children:
            if not child.is_active(config, rt):
                return False
        return True

    def directories_to_remove(self, config: Config) -> List[str]:
        return matrix.flatten(
            [child.directories_to_remove(config) for child in self.children]
        )

    def run(self, config: Config, rt: Runtime) -> int:
        for child in self.children:
            result = child.run(config, rt)
            if result:
                return result
        return 0


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
            copy = Runtime(rt)
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
    @abstractmethod
    def command(self, statement: Statement) -> List[str]: ...

    def run(self, statement: Statement, rt: Runtime):
        return 1

    @classmethod
    def statement(
        cls, outputs: List[str], inputs: List[str], implicit_deps: List[str] = []
    ):
        return Statement(cls(), outputs, inputs, implicit_deps)


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


__steps: List[Step] = []


def register_step(step: Step):
    global __steps

    name = step.name
    if name in [step.name for step in __steps]:
        raise NameError(f"Step {name} already registered")

    __steps.append(step)
