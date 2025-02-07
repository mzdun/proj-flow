# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.python.steps** defines steps for building, installing and
documenting.
"""

import importlib

from proj_flow.api import env, step

from . import rtdocs


@step.register
class Install:
    name = "Install"

    def platform_dependencies(self):
        return ["python -m pip"]

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        return rt.cmd("python", "-m", "pip", "install", rt.root)


@step.register
class Build:
    name = "Build"

    def platform_dependencies(self):
        return ["python -m build"]

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        build_main = importlib.import_module("build.__main__")
        build_main.main([], "proj-flow build")
        return 0
