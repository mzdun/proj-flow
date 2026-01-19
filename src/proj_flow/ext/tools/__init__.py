# Copyright (c) 2026 Marcin Zdun
# This file is licensed under MIT license (see LICENSE for details)

from proj_flow.api import arg
from proj_flow.ext.tools.pragma_once import pragma_once
from proj_flow.ext.tools.run_linter import run_linter

__all__ = ["tools", "pragma_once", "run_linter"]


@arg.command("tools")
def tools():
    """Run various C++ tools and helpers"""
