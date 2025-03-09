# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
import sys

src_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src"
)
sys.path.insert(0, src_dir)

import proj_flow  # noqa: E402, pylint: disable=wrong-import-position

print("\ntesting proj-flow", proj_flow.__version__)
