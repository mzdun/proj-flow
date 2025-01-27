# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import argparse
import json
import os
import sys
from typing import Annotated, Optional

from ...flow.arg import FlagArgument
from ...flow.config import Configs, Runtime
from . import matrix

__all__ = ["matrix", "command_ci"]


def command_ci(rt: Runtime):
    """Supplies data for github actions"""
