# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.hosting** contains links information for various
hosting services. Currently, only GitHub is supported.
"""

from . import github

__all__ = ["github"]
