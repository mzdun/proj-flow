# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.test_runner** provides the ``tests runner`` command, which runs data-driven
test cases against binaries built with a CMake preset.
"""

from proj_flow.ext.test_runner import cli

__all__ = ["cli"]
