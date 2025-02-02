# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.base.plugins** provide the plugin enumeration helpers.
"""

import importlib
import os
from types import ModuleType
from typing import Optional


def _load_plugins(directory: str, package: Optional[str], can_fail=False):
    for _, dirnames, filenames in os.walk(directory):
        for dirname in dirnames:
            if dirname == "__pycache__":
                continue

            try:
                importlib.import_module(f".{dirname}", package=package)
            except ModuleNotFoundError as err:
                if not can_fail:
                    raise err
        for filename in filenames:
            if filename == "__init__.py":
                continue

            try:
                importlib.import_module(
                    f".{os.path.splitext(filename)[0]}", package=package
                )
            except ModuleNotFoundError as err:
                if not can_fail:
                    raise err
        dirnames[:] = []


def load_module_plugins(mod: ModuleType, can_fail=False):
    spec = mod.__spec__
    if not spec:
        return
    for location in spec.submodule_search_locations:
        _load_plugins(location, spec.name, can_fail)
