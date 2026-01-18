# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.webidl** provides ``webidl init``, ``webidl cmake``,
``webidl depfile``and ``webidl gen`` commands, allowing for simple
WebIDL/mustache generation.
"""

from . import cli

__all__ = ["cli"]
