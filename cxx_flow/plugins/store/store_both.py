# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from cxx_flow.api.step import SerialStep, register_step

from .store_packages import StorePackages
from .store_tests import StoreTests


class StoreBoth(SerialStep):
    name = "Store"

    def __init__(self):
        super().__init__()
        self.children = [StoreTests(), StorePackages()]


register_step(StoreBoth())
