# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.cplusplus.cmake.steps** defines steps for configuring,
building and archiving.
"""

import os
from typing import Dict, List, cast

from proj_flow import api
from proj_flow.api import env, step
from proj_flow.base.__cmake_version__ import CMAKE_VERSION


class CMakeBase(api.step.Step):
    _name: str
    _runs_after: List[str] = []
    _runs_before: List[str] = []

    @property
    def name(self):
        return self._name

    @property
    def runs_after(self):
        return self._runs_after

    @property
    def runs_before(self):
        return self._runs_before

    def __init__(
        self, name: str, runs_after: List[str] = [], runs_before: List[str] = []
    ):
        super().__init__()
        self._name = name
        self._runs_after = runs_after
        self._runs_before = runs_before

    def is_active(self, config: api.env.Config, rt: api.env.Runtime) -> int:
        return os.path.isfile("CMakeLists.txt") and os.path.isfile("CMakePresets.json")

    def platform_dependencies(self):
        return [f"cmake>={CMAKE_VERSION}"]

    def dep_with_tool(self, tool: str):
        return [f"cmake>={CMAKE_VERSION}", f"{tool}>={CMAKE_VERSION}"]


@step.register
class CMakeConfig(CMakeBase):
    """Configures the project using ``preset`` config."""

    def __init__(self):
        super().__init__(name="CMake")

    def is_active(self, config: env.Config, rt: env.Runtime) -> int:
        return os.path.isfile("CMakeLists.txt") and os.path.isfile("CMakePresets.json")

    def directories_to_remove(self, config: env.Config) -> List[str]:
        return [f"build/{config.build_type}"]

    def run(self, config: env.Config, rt: env.Runtime) -> int:
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


@step.register()
class CMakeBuild(CMakeBase):
    """Builds the project using ``preset`` config."""

    def __init__(self):
        super().__init__(name="Build", runs_after=["CMake"])

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        return rt.cmd("cmake", "--build", "--preset", config.preset, "--parallel")


@step.register
class CMakeTest(CMakeBase):
    """Runs tests in the project using ``preset`` config."""

    def __init__(self):
        super().__init__(name="Test", runs_after=["Build"])

    def platform_dependencies(self):
        return self.dep_with_tool("ctest")

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        return rt.cmd("ctest", "--preset", config.preset)


@step.register
class PackStep(CMakeBase):
    """
    Packs archives and installers from ``cpack_generator`` config, using
    ``preset`` config.
    """

    def __init__(self):
        super().__init__(name="Pack", runs_after=["Build"])

    def platform_dependencies(self):
        return self.dep_with_tool("cpack")

    def is_active(self, config: env.Config, rt: env.Runtime) -> int:
        return (
            super().is_active(config, rt)
            and len(config.items.get("cpack_generator", [])) > 0
        )

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        generators = ";".join(config.items.get("cpack_generator", []))
        return rt.cmd("cpack", "--preset", config.preset, "-G", generators)
