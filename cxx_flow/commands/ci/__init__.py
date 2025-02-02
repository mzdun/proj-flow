# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.commands.ci** implements ``./flow ci`` command.
"""

from cxx_flow.api import arg, env

from . import matrix

__all__ = ["matrix", "command_ci"]


@arg.command("ci")
def command_ci(rt: env.Runtime):
    """Perform various CI tasks"""
