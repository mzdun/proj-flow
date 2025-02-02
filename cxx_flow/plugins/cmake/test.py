# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.plugins.cmake.test** provides ``"Test"`` step.
"""

import os

from cxx_flow.api import env, step

from .__version__ import CMAKE_VERSION


@step.register
class CMakeTest:
    """Runs tests in the project using ``preset`` config."""

    name = "Test"
    runs_after = ["Build"]

    def platform_dependencies(self):
        return [f"cmake>={CMAKE_VERSION}", f"ctest>={CMAKE_VERSION}"]

    def is_active(self, config: env.Config, rt: env.Runtime) -> int:
        return os.path.isfile("CMakeLists.txt") and os.path.isfile("CMakePresets.json")

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        return rt.cmd("ctest", "--preset", config.preset)
