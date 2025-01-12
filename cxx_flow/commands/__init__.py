# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import importlib
import os

top = os.path.dirname(__file__)
for _, dirnames, filenames in os.walk(top):
    dirnames[:] = []
    for filename in filenames:
        if filename.startswith("-"):
            continue
        importlib.import_module(
            f".{os.path.splitext(filename)[0]}", "cxx_flow.commands"
        )
