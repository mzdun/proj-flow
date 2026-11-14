# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.webidl.cli.root** declares the ``webidl`` command group.
"""

from typing import cast

from proj_flow.api import arg
from proj_flow.base import inspect as _inspect


@arg.command("webidl")
def webidl():
    """Configure and generate WebIDL-based interfaces"""
