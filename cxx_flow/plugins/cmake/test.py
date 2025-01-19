# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os

from cxx_flow.flow.config import Config, Runtime
from cxx_flow.flow.step import Step, register_step

from .__version__ import CMAKE_VERSION


class CMakeTest(Step):
    name = "Test"
    runs_after = ["Build"]

    def platform_dependencies(self):
        return [f"cmake>={CMAKE_VERSION}", f"ctest>={CMAKE_VERSION}"]

    def is_active(self, config: Config, rt: Runtime) -> int:
        return os.path.isfile("CMakeLists.txt") and os.path.isfile("CMakePresets.json")

    def run(self, config: Config, rt: Runtime) -> int:
        return rt.cmd("ctest", "--preset", config.preset)


register_step(CMakeTest())
