# Copyright (c) 2026 Marcin Zdun
# This file is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.tools** provides the ``tools`` command group, with
``tools pragma-once`` and ``tools run-linter`` commands.
"""

from proj_flow.api import arg
from proj_flow.ext.tools import pragma_once, run_linter

__all__ = ["tools", "pragma_once", "run_linter"]


@arg.command("tools")
def tools():
    """Run various C++ tools and helpers"""
