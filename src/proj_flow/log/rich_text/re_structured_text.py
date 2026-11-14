# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.rich_text.re_structured_text** provides details of making
reStructuredText changelogs.
"""

from typing import List

from proj_flow.log import commit, msg
from proj_flow.log.rich_text import api


class FileUpdate(api.FileUpdate):
    """
    New section of a reStructuredText changelog, describing a release.

    :param setup: log setup of the release
    :param commit_date: date of the release, as ``YYYY-MM-DD``
    """

    def __init__(self, setup: commit.LogSetup, commit_date: str):
        super().__init__(setup, commit_date)

    def intro_lines(self) -> List[str]:
        version = (self.setup.curr_tag or " *unknown*")[1:]
        compare = self.setup.commit_listing_link()

        if compare:
            heading = f"`{version} <{compare}>`_ ({self.commit_date})"
        else:
            heading = f"{version} ({self.commit_date})"

        return [
            heading,
            "=" * len(heading),
            "",
        ]

    def section_header(self, lines: List[str], header):
        lines.extend([header, "-" * len(header), ""])

    def summary(self, text: str) -> str:
        return text.replace("`", "``")

    def outro_lines(self, lines: List[str]) -> None:
        """
        Add nothing after the last section; the changelog file has no
        "Full Changelog" line, as the release heading links to the commit
        listing instead, when the hosting provides one.

        :param lines: lines of the message, left unchanged
        """
        pass

    def short_hash_link(self, link: commit.Link):
        url = self.setup.single_commit_link(link)
        if not url:
            return link.short_hash
        return f"`{link.short_hash} <{url}>`_"


class ChangelogGenerator(api.ChangelogGenerator):
    """
    Generator of ``CHANGELOG.rst``, with each release under a title linking
    to its commit listing.
    """

    @property
    def ext(self) -> str:
        return ".rst"

    @property
    def split_re(self) -> str:
        # linked heading from a hosting service, or a plain one without it
        return r"\n(?:`[0-9]+\.[0-9]+[^>]+\>`\_|[0-9]+\.[0-9]+\S*) \([^)]+\)\n==+\n"

    @property
    def formatter(self):
        return FileUpdate

    def main_heading(self, caption: str) -> List[str]:
        line = "=" * len(caption)
        return [line, caption, line, ""]

    def para(self, text: str) -> List[str]:
        return [msg.CommitMessage.wrap_at_78(text), ""]
