# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.log.rich_text** allows to operate on CHANGELOG.md.
"""

from . import api, markdown, re_structured_text

__all__ = ["api", "markdown", "re_structured_text"]


def select_generator(rst: bool = False) -> api.ChangelogGenerator:
    """
    Selects proper generator/formatter for Changelog messages.

    :param rst: Generator selector. When true, returns reStructuredText
        generator, Markdown otherwise.
    """
    if rst:
        return re_structured_text.ChangelogGenerator()
    return markdown.ChangelogGenerator()
