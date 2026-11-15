# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.run** implements ``./flow run`` command.
"""

import os
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, List, Optional, Set, cast

from proj_flow import api, dependency
from proj_flow.base import matrix
from proj_flow.flow.configs import Configs


@api.arg.command("run")
def main(
    configs: Configs,
    rt: api.env.Runtime,
    cli_steps: Annotated[
        Optional[List[str]],
        api.arg.Argument(
            help="Run only listed steps; if missing, run all the steps",
            names=["-s", "--steps"],
            nargs="*",
            meta="step",
            action="store",
            default=[],
            completer=api.completers.step_completer,
        ),
    ],
):
    """Run automation steps for current project"""

    with prep_environment(rt, "run-env"):
        rt_steps = cast(List[api.step.Step], rt.steps)
        if not cli_steps:
            steps = [step.name for step in rt_steps]
        else:
            steps = matrix.flatten(step.split(",") for step in cli_steps)
        steps = list(map(lambda s: s.lower(), steps))

        step_names = set(steps)
        program = [step for step in rt_steps if step.name.lower() in step_names]

        errors = gather_dependencies_for_all_configs(configs, rt, program)
        if len(errors) > 0:
            if not rt.silent:
                for error in errors:
                    print(f"proj-flow: {error}", file=sys.stderr)
            return 1

        printed = refresh_directories(configs, rt, program)
        run_steps(configs, rt, program, printed)
        return 0


def gather_dependencies_for_all_configs(
    configs: Configs, rt: api.env.Runtime, steps: List[api.step.Step]
):
    """
    Check the dependencies of the steps active in any of the usable configs.

    :param configs: run configurations
    :param rt: runtime of the run
    :param steps: steps selected to run
    :returns: error messages; empty, if all dependencies are met
    """
    deps: List[dependency.Dependency] = []
    for config in configs.usable:
        active_steps = [step for step in steps if step.is_active(config, rt)]
        deps.extend(dependency.gather(active_steps))
    return dependency.verify(deps)


def refresh_directories(
    configs: Configs, rt: api.env.Runtime, steps: List[api.step.Step]
):
    """
    Remove the directories listed by the steps active in any of the usable
    configs. In dry run mode, the directories are only listed.

    :param configs: run configurations
    :param rt: runtime of the run
    :param steps: steps selected to run
    :returns: ``True``, if any directory was listed on stderr
    """
    directories_to_refresh: Set[Path] = set()
    for config in configs.usable:
        for step in steps:
            if step.is_active(config, rt):
                dirs = step.directories_to_remove(config)
                directories_to_refresh.update(dirs)

    printed = False
    for dirname in directories_to_refresh:
        if not rt.silent:
            printed = True
            print(f"[-] {dirname.as_posix()}", file=sys.stderr)
        if not rt.dry_run:
            shutil.rmtree(dirname, ignore_errors=True)

    return printed


COMPILER_ENV = ["CC", "CXX"]


@contextmanager
def compilers_env_setup(compiler: List[str], rt: api.env.Runtime):
    """
    Set ``$CC`` and ``$CXX`` to the compilers of the config and, on exit,
    restore their original values, removing the ones, which were not set
    before. On Windows, the environment is left untouched.

    :param compiler: C and C++ compilers, as found in the ``compiler`` field
        of the config
    :param rt: runtime used to report the changes
    """
    # only the variables set here are restored on exit; on Windows, nothing
    # is set, so the environment is left alone
    orig_env: dict[str, Optional[str]] = {}
    if sys.platform != "win32":
        for var, value in zip(COMPILER_ENV, compiler):
            orig_env[var] = os.environ.get(var)
            os.environ[var] = value
            rt.message(f"set {var}={value}")
    try:
        yield
    finally:
        for var, value in orig_env.items():
            if value is None:
                os.environ.pop(var, None)
                rt.message(f"unset {var}")
            else:
                os.environ[var] = value
                rt.message(f"set {var}={value}")


def run_steps(
    configs: Configs, rt: api.env.Runtime, program: List[api.step.Step], printed: bool
) -> None:
    """
    Run the active steps for each usable config, with the compilers and the
    ``run-env.<step>`` environment of each step set up. Stops at the first
    failed step.

    :param configs: run configurations
    :param rt: runtime of the run
    :param program: steps selected to run
    :param printed: ``True``, if anything was already printed on stderr, so
        the first config needs a separating empty line
    :raises StepFailed: a step has failed
    """
    config_count = len(configs.usable)
    steps_ran = 0
    for config_index in range(config_count):
        config = configs.usable[config_index]
        steps = [step for step in program if step.is_active(config, rt)]
        step_count = len(steps)
        if step_count == 0:
            continue

        if printed:
            print(file=sys.stderr)
        printed = True

        build_name: Optional[str] = getattr(config, "build_name")

        if build_name:
            if config_count < 2:
                print(f"- {build_name}", file=sys.stderr)
            else:
                print(
                    f"- {config_index + 1}/{config_count}: {build_name}",
                    file=sys.stderr,
                )

        compilers: List[str] = getattr(config, "compiler", [])
        with compilers_env_setup(compilers, rt):
            for index in range(step_count):
                step = steps[index]
                print(
                    f"-- step {index + 1}/{step_count}: {step.name}",
                    file=sys.stderr,
                )
                steps_ran += 1
                with prep_environment(rt, f"run-env.{step.name}"):
                    step.run(config, rt)

    if steps_ran == 0:
        print("Nothing to do.", file=sys.stderr)


@contextmanager
def prep_environment(rt: api.env.Runtime, key: str):
    """
    Set the environment variables listed under ``key`` in the flow config
    and, on exit, restore their original values. Variables with ``null``
    value are removed from the environment.

    :param rt: runtime with the flow config
    :param key: name of the config item with the variables, e.g. ``run-env``
        or ``run-env.<step>``
    """
    original_env = dict[str, str | None]()

    for name, value in cast(dict, rt.items.get(key, {})).items():
        original_value = os.environ.get(name)
        if value is None:
            if original_value is not None:
                del os.environ[name]
                original_env[name] = original_value
                rt.print("export", f"{name}=")
        else:
            os.environ[name] = str(value)
            original_env[name] = original_value
            rt.print("export", f"{name}={value}")

    try:
        yield
    finally:
        for name, value in original_env.items():
            if value is None:
                os.environ.pop(name, None)
                rt.print("export", f"{name}=")
            else:
                os.environ[name] = value
                rt.print("export", f"{name}={value}")
