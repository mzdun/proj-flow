# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.project.cplusplus** registers a ``"C++"`` projects support.
"""

from proj_flow.base import path_get
from proj_flow.project import api

CPP_EXTENSIONS = [
    "proj_flow.ext.cplusplus",
    "proj_flow.ext.sign",
    "proj_flow.ext.store",
]


@api.project_type.add
class CPlusPlus(api.ProjectType):
    def __init__(self):
        super().__init__("C++ plus CMake plus Conan", "cxx")

    def get_extension_list(self, context: dict):
        extensions = [*CPP_EXTENSIONS]
        if path_get(context, "with.github.actions"):
            extensions.append("proj_flow.ext.github")
        if path_get(context, "with.github.social"):
            # keeps the version dropdown in bug_report.yaml in sync with releases
            extensions.append("proj_flow.minimal.ext.bug_report")
        return extensions


cxx = api.get_project_type("cxx")
