# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.base.name_list** provides name list helper for arguments with
choices
"""

from typing import List


def name_list(names: List[str]) -> str:
    if len(names) == 0:
        return ""

    prefix = ", ".join(names[:-1])
    if prefix:
        prefix += " and "
    return f"{prefix}{names[-1]}"
