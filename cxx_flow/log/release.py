# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.log.release** builds a changelog message for hosting
service release.
"""

from typing import List

from cxx_flow.log import commit, msg


class ReleaseMessage(msg.ChangelogMessage):
    setup: commit.LogSetup

    def __init__(self, setup: commit.LogSetup):
        self.setup = setup

    def scope_text(self, scope: str):
        if len(scope):
            scope = f"**{scope}**: "
        return scope

    def short_hash_link(self, link: commit.Link):
        url = self.setup.single_commit_link(link)
        if not url:
            return link.short_hash
        return f"[{link.short_hash}]({url})"

    def outro_lines(self, lines: List[str]) -> None:
        url = self.setup.commit_listing_link()
        if url:
            lines.append(f"**Full Changelog**: {url}")
