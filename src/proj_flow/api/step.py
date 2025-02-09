# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.api.step** exposes APIs used by run extensions.
"""

import os
from abc import ABC, abstractmethod
from typing import List, cast

from proj_flow.api.env import Config, Runtime
from proj_flow.base import inspect as _inspect
from proj_flow.base import matrix
from proj_flow.base.name_list import name_list


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


__steps: List[Step] = []


def _register_step(step: Step):
    global __steps

    name = step.name
    if name in [step.name for step in __steps]:
        if "READTHEDOCS" not in os.environ:
            raise NameError(f"Step {name} already registered")

    __steps.append(step)


def _inherits_from(base, existing_class):
    bases = list(existing_class.__bases__)
    for b in bases:
        if b == base or _inherits_from(base, b):
            return True
    return False


def _extend(existing_class, base):
    if _inherits_from(base, existing_class):
        return existing_class

    bases = list(existing_class.__bases__)
    bases.insert(0, base)

    new_class_namespace = existing_class.__dict__.copy()
    del new_class_namespace["__dict__"]

    metaclass = getattr(existing_class, "__metaclass__", type)
    return metaclass(existing_class.__name__, tuple(bases), new_class_namespace)


def _name_list(label: str, names: List[str], template="`{}`") -> str:
    if len(names) == 0:
        return ""

    joined = name_list([template.format(name) for name in names])
    return f"\n:{label}: {joined}"


def _make_private(f: _inspect.Function):
    if f.__doc__:
        f.__doc__ += "\n\n:meta private:\n"
    else:
        f.__doc__ = ":meta private:\n"


_dummy_config = Config(
    {
        "os": "${os}",
        "build_type": "${build_type}",
        "build_name": "${build_name}",
        "preset": "${preset}",
        "build_generator": "${build_generator}",
    },
    [],
)


def _extend_docstring(conv, step: Step):
    info = "".join(
        (
            f"\n:Name: `{step.name}`",
            _name_list("Runs after", step.runs_after),
            _name_list("Runs before", step.runs_before),
            _name_list("Requires", step.platform_dependencies(), template="``{}``"),
            _name_list(
                "Removes",
                step.directories_to_remove(_dummy_config),
                template="``{}``",
            ),
        )
    )

    doc = conv.__doc__ or "*Docstring is missing!*"
    conv.__doc__ = f"{doc}\n{info}"

    _make_private(conv.is_active)
    _make_private(conv.run)
    _make_private(conv.platform_dependencies)
    _make_private(conv.directories_to_remove)


def register(cls=None):
    def impl(cls):
        conv = _extend(cls, Step)
        step = cast(Step, conv())
        _register_step(step)
        _extend_docstring(conv, step)

        return conv

    if cls is None:
        return impl

    return impl(cls)


def verbose_info():
    for step in __steps:
        print(
            f'-- Step: adding "{step.name}" from `{step.__module__}.{step.__class__.__name__}`'
        )
