# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.cplusplus.cmake.version** provides project suite plugin.
"""

from typing import NamedTuple, Optional

from proj_flow.api import env, release
from proj_flow.ext.cplusplus.cmake.parser import get_project


class QuickProjectInfo(NamedTuple):
    name: Optional[str] = None
    path: Optional[str] = None
    pattern: Optional[str] = None


@release.project_suites.add
class ProjectSuite(release.ProjectSuite):
    def get_project(self, rt: env.Runtime) -> Optional[release.Project]:
        project = get_project(rt.root)
        if project is None:
            return None
        return release.Project(
            project.name.value, release.Version(project.version, project.stability)
        )

    def get_version_file_path(self, rt: env.Runtime) -> Optional[str]:
        return "CMakeLists.txt"
