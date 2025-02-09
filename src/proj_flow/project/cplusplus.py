# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.project.cplusplus** registers a ``"C++"`` projects support.
"""

from proj_flow.project import api


@api.project_type.add
class CPlusPlus(api.ProjectType):
    def __init__(self):
        super().__init__("C++ + CMake + Conan", "cxx")


project = api.get_project_type("cxx")
