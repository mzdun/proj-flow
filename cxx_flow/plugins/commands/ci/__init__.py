# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.plugins.commands.ci** implements ``./flow ci`` command.
"""

from cxx_flow.api import arg, env

from . import matrix

__all__ = ["matrix", "command_ci"]


@arg.command("ci")
def main():
    """Perform various CI tasks"""
