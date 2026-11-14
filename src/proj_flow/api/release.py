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
    """
    Value found in a project file, together with its position, so it can be
    replaced in place by :meth:`ProjectSuite.patch_project`.
    """

    #: Text of the value, without any quotes.
    value: str

    #: Offset of the value in the file, or ``-1``, if it is not in the file.
    offset: int


#: Value missing from the project file.
NO_ARG = Arg("", -1)


class Decl(NamedTuple):
    """
    Named value found in a project file, together with its position.
    """

    #: Name of the declaration.
    name: str

    #: Text of the value.
    value: str

    #: Offset of the value in the file.
    offset: int

    def __str__(self):
        return self.value

    def asArg(self):
        """
        Drop the name.

        :returns: the value with its position
        """
        return Arg(self.value, self.offset)


class Version(NamedTuple):
    """
    Project version, split into the parts, which are patched separately.
    """

    #: Core version, ``major.minor.patch``.
    core: Arg

    #: Pre-release part, everything after the core, e.g. ``-rc.1``; empty
    #: for a release.
    stability: Arg

    def __str__(self):
        return f"{self.core.value}{self.stability.value}"


@dataclass
class Project:
    """
    Name and version of the project, as read by a :class:`ProjectSuite`.
    """

    #: Name of the project, used as the base of the package names.
    package_root: str

    #: Current version of the project.
    version: Version

    @property
    def archive_name(self):
        """Base name of the packages, ``<name>-<version>``."""
        return f"{self.package_root}-{self.version}"

    @property
    def tag_name(self):
        """Name of the version tag, ``v<version>``."""
        return f"v{self.version}"

    @property
    def package_prefix(self):
        """
        Prefix of the package file names, used to find the packages to
        upload to a release.
        """
        return f"{self.archive_name}-"

    @property
    def package_suffix(self) -> str:
        """
        Suffix of the package file names, used to find the packages to
        upload to a release; empty by default.
        """
        return ""


class ProjectSuite(ABC):
    """
    Extension point for project kinds (CMake, Python, ...), registered with
    :data:`project_suites`. A suite reads the project name and version from
    the project files and writes the new version during a release.
    """

    @abstractmethod
    def get_project(self, rt: env.Runtime) -> Optional[Project]:
        """
        Read the project information, if the project at :attr:`rt.root
        <proj_flow.api.env.FlowConfig.root>` is of this kind.

        :param rt: runtime with the project root
        :returns: the project, or ``None``, if this suite does not recognize
            it
        """
        ...

    def set_version(self, rt: env.Runtime, version: str):
        """
        Write a new version to the project files, patching the core and the
        stability parts separately.

        :param rt: runtime with the project root
        :param version: new version, without the ``v`` prefix, e.g.
            ``1.2.3`` or ``1.2.3-rc.1``
        """
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
    def get_version_file_path(self, rt: env.Runtime) -> Optional[str]:
        """
        Path to the file holding the version, patched by
        :meth:`patch_project` and committed with the release.

        :param rt: runtime with the project root
        :returns: path to the file, or ``None``, if there is none
        """
        ...

    def patch_project(self, rt: env.Runtime, pos: Arg, newValue: str):
        """
        Replace a value in the version file in place. Does nothing, if the
        suite has no version file.

        :param rt: runtime with the project root
        :param pos: current value and its position in the version file
        :param newValue: text to put in place of the current value
        """
        path = self.get_version_file_path(rt)

        if not path or not os.path.isfile(path):
            return

        with open(path, "r", encoding="UTF-8") as input:
            text = input.read()

        patched = text[: pos.offset] + newValue + text[pos.offset + len(pos.value) :]

        with open(path, "w", encoding="UTF-8") as input:
            input.write(patched)


#: Registry of known project kinds.
project_suites = registry.Registry[ProjectSuite]("ProjectSuite")


def get_project(rt: env.Runtime):
    """
    Read the project information with the first suite, which recognizes the
    project. Exits the program, if none does.

    :param rt: runtime with the project root
    :returns: the project
    """

    def wrap(suite: ProjectSuite):
        return suite.get_project(rt)

    _, project = project_suites.find(wrap)
    if project is None:
        rt.fatal(f"Cannot get project information from {rt.root.as_posix()}")
    return project
