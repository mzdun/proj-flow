# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.python.steps** defines steps for building, installing and
documenting.
"""

import importlib
import os

from proj_flow.api import env, release, step

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


@step.register
class CheckTwine:
    name = "Check Twine"

    runs_after = ["Build"]

    def platform_dependencies(self):
        return ["twine"]

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        filenames = []
        for root, dirnames, filenames in os.walk("dist"):
            dirnames[:] = []

        _, project = release.project_suites.find(lambda suite: suite.get_project(rt))
        archive_name = project and project.archive_name
        if archive_name:
            dot_suffix = f"{archive_name}."
            dash_suffix = f"{archive_name}-"
            filenames = [
                filename
                for filename in filenames
                if filename.startswith(dot_suffix) or filename.startswith(dash_suffix)
            ]

        if len(filenames) == 0:
            return 0

        return rt.cmd(
            "twine", "check", *(os.path.join(root, filename) for filename in filenames)
        )
