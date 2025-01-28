# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from cxx_flow.api.env import Runtime

from . import matrix

__all__ = ["matrix", "command_ci"]


def command_ci(rt: Runtime):
    """Supplies data for github actions"""
