# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
from typing import Dict, List, cast

from cxx_flow import api

from .__version__ import CMAKE_VERSION


@api.step.register
class CMakeConfig:
    name = "CMake"
    runs_after = ["Conan"]

    def platform_dependencies(self):
        return [f"cmake>={CMAKE_VERSION}"]

    def is_active(self, config: api.env.Config, rt: api.env.Runtime) -> int:
        return os.path.isfile("CMakeLists.txt") and os.path.isfile("CMakePresets.json")

    def directories_to_remove(self, config: api.env.Config) -> List[str]:
        return [f"build/{config.build_type}"]

    def run(self, config: api.env.Config, rt: api.env.Runtime) -> int:
        cmake_vars = cast(Dict[str, str], rt._cfg.get("cmake", {}).get("vars", {}))
        defines: List[str] = []
        for var in cmake_vars:
            value = cmake_vars[var]

            is_flag = value.startswith("?")
            if is_flag:
                value = value[1:]

            if value.startswith("config:"):
                value = value[len("config:")]
                value = config.get_path(value)
            elif value.startswith("runtime:"):
                value = value[len("runtime:")]
                value = getattr(rt, value, None)

            if is_flag:
                value = "ON" if value else "OFF"

            defines.append(f"-D{var}={value}")

        return rt.cmd(
            "cmake",
            "--preset",
            f"{config.preset}-{config.build_generator}",
            *defines,
        )
