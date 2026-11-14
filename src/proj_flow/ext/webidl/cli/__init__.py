# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.webidl.cli** registers the ``webidl`` command with its ``init``,
``cmake``, ``depfile`` and ``gen`` subcommands.
"""

from proj_flow.ext.webidl.cli import cmake, depfile, gen, init, root

__all__ = ["root", "init", "cmake", "depfile", "gen"]
