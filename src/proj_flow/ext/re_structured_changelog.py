# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.re_structured_changelog** registers a
:class:`api.ChangelogGenerator` plugin implemented for reStructuredText
changelogs.
"""

from proj_flow.log.rich_text.api import changelog_generators
from proj_flow.log.rich_text.re_structured_text import ChangelogGenerator


@changelog_generators.add
class Plugin(ChangelogGenerator):
    pass
