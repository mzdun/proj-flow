# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.plugins.commands.ci** implements ``./flow ci`` command.
"""

from proj_flow.api import arg

from . import changelog, matrix, release

__all__ = ["changelog", "matrix", "release"]


@arg.command("ci")
def main():
    """Perform various CI tasks"""
