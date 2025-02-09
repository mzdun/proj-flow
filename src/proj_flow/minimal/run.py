# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.run** implements ``./flow run`` command.
"""

import os
import shutil
import sys
from contextlib import contextmanager
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
    return run_steps(configs, rt, program, printed)


def gather_dependencies_for_all_configs(
    configs: Configs, rt: api.env.Runtime, steps: List[api.step.Step]
):
    deps: List[dependency.Dependency] = []
    for config in configs.usable:
        active_steps = [step for step in steps if step.is_active(config, rt)]
        deps.extend(dependency.gather(active_steps))
    return dependency.verify(deps)


def refresh_directories(
    configs: Configs, rt: api.env.Runtime, steps: List[api.step.Step]
):
    directories_to_refresh: Set[str] = set()
    for config in configs.usable:
        for step in steps:
            if step.is_active(config, rt):
                dirs = step.directories_to_remove(config)
                directories_to_refresh.update(dirs)

    printed = False
    for dirname in directories_to_refresh:
        if not rt.silent:
            printed = True
            print(f"[-] {dirname}", file=sys.stderr)
        if not rt.dry_run:
            shutil.rmtree(dirname, ignore_errors=True)

    return printed


COMPILER_ENV = ["CC", "CXX"]


@contextmanager
def compilers_env_setup(compiler: List[str], rt: api.env.Runtime):
    orig_env = {}
    if sys.platform != "win32":
        for var, value in zip(COMPILER_ENV, compiler):
            if var in os.environ:
                orig_env[var] = os.environ[var]
            os.environ[var] = value
            rt.message(f"set {var}={value}")
    try:
        yield
    finally:
        for var in COMPILER_ENV:
            if var in os.environ:
                del os.environ[var]
            if var not in orig_env:
                rt.message(f"unset {var}")
        for var, value in orig_env.items():
            os.environ[var] = value
            rt.message(f"set {var}={value}")


def run_steps(
    configs: Configs, rt: api.env.Runtime, program: List[api.step.Step], printed: bool
) -> int:
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
                print(f"-- step {index + 1}/{step_count}: {step.name}", file=sys.stderr)
                steps_ran += 1
                ret = step.run(config, rt)
                if ret:
                    return 1

    if steps_ran == 0:
        print("Nothing to do.")

    return 0
