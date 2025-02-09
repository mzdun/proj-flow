# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal** defines minimal extension package: ``bootstrap``
and ``run`` commands, with basic set of steps.
"""

from . import bootstrap, init, list, run, system

__all__ = ["bootstrap", "init", "list", "run", "system"]
