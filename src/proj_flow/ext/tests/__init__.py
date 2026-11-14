# Copyright (c) 2026 Marcin Zdun
# This file is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.tests** provides the ``tests`` command group and the
``"JUnitToCtrf"`` step.
"""

from proj_flow.api import arg
from proj_flow.ext.tests import steps

__all__ = ["tests", "steps"]


@arg.command("tests")
def tests():
    """Use test helpers and runners"""
