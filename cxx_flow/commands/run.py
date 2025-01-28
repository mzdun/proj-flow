# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)


import shutil
import sys
from typing import Annotated, List, Optional, Set, cast

from cxx_flow import api
from cxx_flow.base import matrix
from cxx_flow.flow import dependency
from cxx_flow.flow.configs import Configs


def command_run(
    steps: Annotated[
        Optional[List[str]],
        api.arg.Argument(
            help="run only listed steps; if missing, run all the steps",
            names=["-s", "--steps"],
            nargs="*",
            meta="step",
            action="append",
            default=[],
        ),
    ],
    configs: Configs,
    rt: api.env.Runtime,
):
    """Runs automation steps for current project"""

    rt_steps = cast(List[api.step.Step], rt.steps)
    steps = matrix.flatten(step.split(",") for step in matrix.flatten(steps))
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


def run_steps(
    configs: Configs, rt: api.env.Runtime, program: List[api.step.Step], printed: bool
) -> int:
    config_count = len(configs.usable)
    for config_index in range(config_count):
        config = configs.usable[config_index]
        steps = [step for step in program if step.is_active(config, rt)]
        step_count = len(steps)
        if step_count == 0:
            continue

        if printed:
            print(file=sys.stderr)
        printed = True

        if config_count < 2:
            print(f"- {config.build_name}", file=sys.stderr)
        else:
            print(
                f"- {config_index + 1}/{config_count}: {config.build_name}",
                file=sys.stderr,
            )
        for index in range(step_count):
            step = steps[index]
            print(f"-- step {index + 1}/{step_count}: {step.name}", file=sys.stderr)
            ret = step.run(config, rt)
            if ret:
                return 1

    return 0
