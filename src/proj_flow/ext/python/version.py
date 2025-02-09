# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.python.version** provides project suite plugin.
"""

import os
import re
from typing import NamedTuple, Optional

import toml

from proj_flow.api import env, release


class QuickProjectInfo(NamedTuple):
    name: Optional[str] = None
    path: Optional[str] = None
    pattern: Optional[str] = None


@release.project_suites.add
class ProjectSuite(release.ProjectSuite):
    def get_project(self, rt: env.Runtime) -> Optional[release.Project]:
        name, path, pattern = self._pyproject_hatch(rt)
        if name is None or path is None:
            return None

        try:
            with open(os.path.join(rt.root, path), encoding="UTF-8") as infile:
                text = infile.read()
        except FileNotFoundError:
            return None

        if pattern is not None:
            candidate = self._check(text, pattern)
            return release.Project(name, candidate) if candidate else None

        for varname in ["__version__", "VERSION"]:
            for end in ['"', "'"]:
                pattern = rf"{varname}\s*=\s*{end}v?(?P<version>[^{end}]+){end}"
                candidate = self._check(text, pattern)
                if candidate:
                    return release.Project(name, candidate)

        return None

    def _check(self, text: str, pattern: str):
        m = re.search(f"^{pattern}", text, flags=re.MULTILINE)
        if not m:
            return None
        version, start = m.group("version"), m.start("version")
        core = re.split(r"([0-9]+\.[0-9]+\.[0-9]+)", version, maxsplit=1)[1]
        stability = version[len(core) :]

        return release.Version(
            release.Arg(core, start), release.Arg(stability, start + len(core))
        )

    def get_version_file_path(self, rt: env.Runtime) -> Optional[str]:
        _, path, _ = self._pyproject_hatch(rt)
        return path

    def _pyproject_hatch(self, rt: env.Runtime):
        pyproject_path = os.path.join(rt.root, "pyproject.toml")
        try:
            data = toml.load(pyproject_path)
            project = data.get("project", {})
            hatch = data.get("tool", {}).get("hatch", {})
            wheels = (
                hatch.get("build", {})
                .get("targets", {})
                .get("wheel", {})
                .get("packages", [])
            )

            name = project.get("name")
            if len(wheels) > 0:
                first_wheel = wheels[0].split("/")[-1]
                if first_wheel:
                    name = first_wheel

            dynamic = project.get("dynamic", [])
            if "version" in dynamic:
                version_dict = hatch.get("version", {})
                return QuickProjectInfo(
                    name=name,
                    path=version_dict.get("path"),
                    pattern=version_dict.get("pattern"),
                )
            return QuickProjectInfo(
                name=name,
                path="pyproject.toml",
            )
        except FileNotFoundError:
            return QuickProjectInfo()
