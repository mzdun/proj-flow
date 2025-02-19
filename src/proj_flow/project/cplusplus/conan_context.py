# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.cplusplus.conan** provides the ``"Conan"`` step.
"""

from proj_flow.project.cplusplus import project

project.cxx.register_switch("with_conan", "Use Conan for dependency manager", True)
