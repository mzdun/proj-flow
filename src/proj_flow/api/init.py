# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.api.init** exposes APIs used by initialization extensions.
"""

from typing import List

from proj_flow.api.env import Runtime


class InitStep:
    def priority(self):
        return 100

    def platform_dependencies(self) -> List[str]:
        return []

    def postprocess(self, rt: Runtime, context: dict):
        pass


__steps: List[InitStep] = []


def register_init_step(step: InitStep):
    global __steps
    __steps.append(step)
