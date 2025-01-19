# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os

from cxx_flow.flow.config import Config, Runtime
from cxx_flow.flow.step import Step, register_step


class StoreTest(Step):
    name = "StoreTest"
    runs_after = ["Test"]

    def run(self, config: Config, rt: Runtime) -> int:
        return rt.cp(
            f"build/{config.preset}/test-results", "build/artifacts/test-results"
        )


register_step(StoreTest())
