# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.project.cplusplus.conan_context** registers the
``with.conan`` switch for new C++ projects.
"""

from proj_flow.project.cplusplus import project

project.cxx.register_switch("with.conan", "Use Conan for dependency manager", True)
