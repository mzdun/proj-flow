# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from cxx_flow.flow.step import SerialStep, register_step

from .store_packages import StorePackages
from .store_test import StoreTest


class StoreBoth(SerialStep):
    name = "Store"

    def __init__(self):
        super().__init__()
        self.children = [StoreTest(), StorePackages()]


register_step(StoreBoth())
