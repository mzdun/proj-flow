# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)


import shutil
import sys
from typing import Annotated, List, Optional, Set, cast

from ..flow import dependency, matrix
from ..flow.arg import Argument
from ..flow.config import Configs, Runtime
from ..flow.step import Step


def command_run(
    steps: Annotated[
        Optional[List[str]],
        Argument(
            help="run only listed steps; if missing, run all the steps",
            names=["-s", "--steps"],
            nargs="*",
            meta="step",
            action="append",
            default=[],
        ),
    ],
    configs: Configs,
    rt: Runtime,
):
    """Runs automation steps for current project"""

    rt_steps = cast(List[Step], rt.steps)
    steps = matrix.flatten(step.split(",") for step in steps)
    if not steps:
        steps = [step.name for step in rt_steps]

    step_names = set(steps)
    program = [step for step in rt_steps if step.name in step_names]

    errors = gather_dependencies_for_all_configs(configs, rt, program)
    if len(errors) > 0:
        if not rt.silent:
            for error in errors:
                print(f"cxx-flow: {error}", file=sys.stderr)
        return 1

    printed = refresh_directories(configs, rt, program)
    run_steps(configs, rt, program, printed)


def gather_dependencies_for_all_configs(
    configs: Configs, rt: Runtime, steps: List[Step]
):
    deps: List[dependency.Dependency] = []
    for config in configs.usable:
        active_steps = [step for step in steps if step.is_active(config, rt)]
        deps.extend(dependency.gather(active_steps))
    return dependency.verify(deps)


def refresh_directories(configs: Configs, rt: Runtime, steps: List[Step]):
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
            print(f"[-] {dirname}")
        if not rt.dry_run:
            shutil.rmtree(dirname, ignore_errors=True)

    return printed


def run_steps(configs: Configs, rt: Runtime, program: List[Step], printed: bool):
    for config in configs.usable:
        steps = [step for step in program if step.is_active(config, rt)]
        step_count = len(steps)
        if step_count == 0:
            continue

        if printed:
            print()
        printed = True

        print("-", config.build_name)
        for index in range(step_count):
            step = steps[index]
            print(f"-- step {index + 1}/{step_count}: {step.name}")
            ret = step.run(config, rt)
            if ret:
                return 1

    return 0
