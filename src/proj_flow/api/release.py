# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.api.release** provides :class:`ProjectSuite` extension point.
"""

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import NamedTuple, Optional, Union

from proj_flow.api import env
from proj_flow.base import registry


class Arg(NamedTuple):
    value: str
    offset: int


NO_ARG = Arg("", -1)


class Decl(NamedTuple):
    name: str
    value: str
    offset: int

    def __str__(self):
        return self.value

    def asArg(self):
        return Arg(self.value, self.offset)


class Version(NamedTuple):
    core: Arg
    stability: Arg

    def __str__(self):
        return f"{self.core.value}{self.stability.value}"


@dataclass
class Project:
    package_root: str
    version: Version

    @property
    def archive_name(self):
        return f"{self.package_root}-{self.version}"

    @property
    def tag_name(self):
        return f"v{self.version}"

    @property
    def package_prefix(self):
        return f"{self.archive_name}-"

    @property
    def package_suffix(self):
        return ""


class ProjectSuite(ABC):
    @abstractmethod
    def get_project(self, rt: env.Runtime) -> Optional[Project]: ...

    def set_version(self, rt: env.Runtime, version: str):
        core = re.split(r"([0-9]+\.[0-9]+\.[0-9]+)", version, maxsplit=1)[1]
        stability = version[len(core) :]

        project = self.get_project(rt)
        if project:
            self.patch_project(rt, project.version.core, core)

        project = self.get_project(rt)
        if project:
            version_pos = project.version

            if len(stability):
                self.patch_project(rt, version_pos.stability, stability)
            elif len(version_pos.stability.value):
                self.patch_project(rt, version_pos.stability, "")

    @abstractmethod
    def get_version_file_path(self, rt: env.Runtime) -> Optional[str]: ...

    def patch_project(self, rt: env.Runtime, pos: Arg, newValue: str):
        path = self.get_version_file_path(rt)

        if not path or not os.path.isfile(path):
            return

        with open(path, "r", encoding="UTF-8") as input:
            text = input.read()

        patched = text[: pos.offset] + newValue + text[pos.offset + len(pos.value) :]

        with open(path, "w", encoding="UTF-8") as input:
            input.write(patched)


project_suites = registry.Registry[ProjectSuite]("ProjectSuite")


def get_project(rt: env.Runtime):
    def wrap(suite: ProjectSuite):
        return suite.get_project(rt)

    _, project = project_suites.find(wrap)
    if project is None:
        rt.fatal(f"Cannot get project information from {rt.root}")
    return project
