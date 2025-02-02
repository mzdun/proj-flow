# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.plugins.store** provides ``"Store"`` step.
"""

from cxx_flow.api import step

from .store_packages import StorePackages
from .store_tests import StoreTests


@step.register
class StoreBoth(step.SerialStep):
    """Stores all artifacts created for ``preset`` config value."""

    name = "Store"

    def __init__(self):
        super().__init__()
        self.children = [StoreTests(), StorePackages()]
