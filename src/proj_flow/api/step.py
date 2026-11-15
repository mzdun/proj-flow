# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.api.step** exposes APIs used by run extensions.
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, cast

from proj_flow.api.env import Config, Runtime, StepFailed
from proj_flow.base import inspect as _inspect
from proj_flow.base import matrix
from proj_flow.base.name_list import name_list


class Step(ABC):
    """
    Single step of ``./flow run``. Plugins register their steps with
    :func:`register`; the steps are then sorted by :attr:`runs_after` and
    :attr:`runs_before` and, for each run configuration, every active step is
    :meth:`run` in that order.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Name of the step, as used by ``./flow run -s`` (case-insensitive), by
        the run aliases in the project config and by :attr:`runs_after` and
        :attr:`runs_before` of other steps. Must be unique among the
        registered steps.
        """
        ...

    @property
    def runs_after(self) -> List[str]:
        """
        Names of the steps, which must run before this one. Names of steps,
        which are not registered, are ignored.
        """
        return []

    @property
    def runs_before(self) -> List[str]:
        """
        Names of the steps, which must run after this one. Names of steps,
        which are not registered, are ignored.
        """
        return []

    def platform_dependencies(self) -> List[str]:
        """
        Tools this step needs, checked before anything runs. Each entry is
        an executable name, optionally with a version requirement, e.g.
        ``cmake>=3.28``; ``python -m <module>`` checks for a Python module.

        :returns: list of required tools
        """
        return []

    def is_active(self, config: Config, rt: Runtime) -> bool:
        """
        Decide, if this step should run for given configuration. Inactive
        steps are not run, their dependencies are not checked and their
        directories are not removed.

        :param config: current run configuration
        :param rt: runtime of the run
        :returns: ``True``, if the step should run
        """
        return True

    def directories_to_remove(self, config: Config) -> List[Path]:
        """
        Directories, which are removed before any step runs, e.g. stale build
        or package directories.

        :param config: current run configuration
        :returns: list of directories to remove
        """
        return []

    @abstractmethod
    def run(self, config: Config, rt: Runtime) -> None:
        """
        Perform the step for given configuration. Raise
        :class:`StepFailed <proj_flow.api.env.StepFailed>` to stop the whole
        run.

        :param config: current run configuration
        :param rt: runtime of the run; respect its ``dry_run`` flag, e.g. by
            calling tools through :meth:`Runtime.cmd()
            <proj_flow.api.env.Runtime.cmd>`
        :raises StepFailed: the step failed to run
        """

        ...


class SerialStep(Step):
    """
    Step built from a sequence of other steps, run one after another. It runs
    after all the steps its children run after and is active only, if all
    its children are.
    """

    #: Steps to run, in order.
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

    def directories_to_remove(self, config: Config) -> List[Path]:
        return matrix.flatten(
            [child.directories_to_remove(config) for child in self.children]
        )

    def run(self, config: Config, rt: Runtime) -> None:
        for child in self.children:
            child.run(config, rt)


__steps: List[Step] = []


def _register_step(step: Step, replace: bool):
    global __steps

    name = step.name

    if replace:
        for index, prev in enumerate(__steps):
            if prev.name == name:
                __steps[index] = step
                return

        if "READTHEDOCS" not in os.environ:
            raise NameError(
                f"Step {name} is marked as replacing, but there is no previous step with that name"
            )

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


def _make_private_property(f):
    if isinstance(f, property):
        _make_private(cast(_inspect.Function, f))
        return


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
                [
                    dirname.as_posix()
                    for dirname in step.directories_to_remove(_dummy_config)
                ],
                template="``{}``",
            ),
        )
    )

    doc = conv.__doc__ or "*Docstring is missing!*"
    conv.__doc__ = f"{doc}\n{info}"

    _make_private_property(conv.name)
    _make_private_property(conv.runs_before)
    _make_private_property(conv.runs_after)
    _make_private(conv.is_active)
    _make_private(conv.run)
    _make_private(conv.platform_dependencies)
    _make_private(conv.directories_to_remove)


def register(cls=None, replace=False):
    """
    Class decorator registering a run step. The class gets :class:`Step`
    added to its bases, if needed, and is instantiated once, without
    arguments. Its docstring is extended with the step name, order and
    dependencies.

    Can be used both as ``@step.register`` and as
    ``@step.register(replace=True)``.

    :param cls: class of the step, when used without parentheses
    :param replace: replace an already registered step with the same name,
        instead of failing
    :returns: the registered class, or the decorator, when ``cls`` is missing
    :raises NameError: a step with the same name is already registered, or
        there is no step to replace
    """

    def impl(cls):
        conv = _extend(cls, Step)
        step = cast(Step, conv())
        _register_step(step, replace)
        _extend_docstring(conv, step)

        return conv

    if cls is None:
        return impl

    return impl(cls)


def verbose_info():
    """
    Print the registered steps with the classes implementing them; used with
    ``--verbose``.
    """
    for step in __steps:
        print(
            f'-- Step: adding "{step.name}" from `{step.__module__}.{step.__class__.__name__}`'
        )


def get_registered(name: str):
    """
    Find a registered step.

    :param name: name of the step
    :returns: the step, or ``None``, if no step has this name
    """
    for step in __steps:
        if step.name == name:
            return step
