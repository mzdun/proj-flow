# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os

from cxx_flow.flow.config import Config, Runtime
from cxx_flow.flow.step import Step, register_step

from .__version__ import CMAKE_VERSION


class PackStep(Step):
    name = "Pack"
    runs_after = ["Build", "Sign"]

    def platform_dependencies(self):
        return [f"cmake>={CMAKE_VERSION}", f"cpack>={CMAKE_VERSION}"]

    def is_active(self, config: Config, rt: Runtime) -> int:
        return (
            os.path.isfile("CMakeLists.txt")
            and os.path.isfile("CMakePresets.json")
            and len(config.items.get("cpack_generator", [])) > 0
        )

    def run(self, config: Config, rt: Runtime) -> int:
        generators = ";".join(config.items.get("cpack_generator", []))
        return rt.cmd("cpack", "--preset", config.preset, "-G", generators)


register_step(PackStep())
