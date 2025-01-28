# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os

from cxx_flow.api import env, step


class StoreTests(step.Step):
    name = "StoreTests"
    runs_after = ["Test"]

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        return rt.cp(
            f"build/{config.preset}/test-results", "build/artifacts/test-results"
        )


step.register_step(StoreTests())
