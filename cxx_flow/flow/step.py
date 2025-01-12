# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from abc import ABC, abstractmethod
from typing import List

from .config import Config, Runtime


class Step(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def runs_after(self) -> List[str]:
        return []

    def platform_dependencies(self) -> List[str]:
        return []

    def is_active(self, config: Config, rt: Runtime) -> bool:
        return True

    def directories_to_remove(self, config: Config) -> List[str]:
        return []

    @abstractmethod
    def run(self, config: Config, rt: Runtime) -> int: ...


__steps: List[Step] = []


def register_step(step: Step):
    global __steps

    name = step.name
    if name in [step.name for step in __steps]:
        raise NameError(f"Step {name} already registered")

    __steps.append(step)
