# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import importlib
import os

top = os.path.dirname(__file__)
for _, dirnames, filenames in os.walk(top):
    for dirname in dirnames:
        importlib.import_module(f".{dirname}", "cxx_flow.commands")
    for filename in filenames:
        if filename == "__init__.py":
            continue
        importlib.import_module(
            f".{os.path.splitext(filename)[0]}", "cxx_flow.commands"
        )
    dirnames[:] = []
