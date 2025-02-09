# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.markdown_changelog** registers a
:class:`api.ChangelogGenerator` plugin implemented for markdown changelogs.
"""

from proj_flow.log.rich_text.api import changelog_generators
from proj_flow.log.rich_text.markdown import ChangelogGenerator


@changelog_generators.add
class Plugin(ChangelogGenerator):
    pass
