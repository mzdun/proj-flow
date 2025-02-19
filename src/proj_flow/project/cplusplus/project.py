# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.project.cplusplus** registers a ``"C++"`` projects support.
"""

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
        with_github_actions = not not context.get("with_github_actions")
        if with_github_actions:
            return [*CPP_EXTENSIONS, "proj_flow.ext.github"]
        return CPP_EXTENSIONS


cxx = api.get_project_type("cxx")
