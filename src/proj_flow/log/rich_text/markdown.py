# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.rich_text.markdown** provides details of making Markdown
changelogs.
"""

from typing import List

from proj_flow.log import commit
from proj_flow.log.rich_text import api


class FileUpdate(api.FileUpdate):
    """
    New section of a Markdown changelog, describing a release.

    :param setup: log setup of the release
    :param commit_date: date of the release, as ``YYYY-MM-DD``
    """

    def __init__(self, setup: commit.LogSetup, commit_date: str):
        super().__init__(setup, commit_date)

    def intro_lines(self) -> List[str]:
        version = (self.setup.curr_tag or " *unknown*")[1:]
        compare = self.setup.commit_listing_link()
        if compare:
            return [f"## [{version}]({compare}) ({self.commit_date})", ""]
        return [f"## {version} ({self.commit_date})", ""]

    def outro_lines(self, lines: List[str]) -> None:
        """
        Add nothing after the last section; the changelog file has no
        "Full Changelog" line, as the release heading links to the commit
        listing instead, when the hosting provides one.

        :param lines: lines of the message, left unchanged
        """
        pass

    def issue_link(self, ref: str):
        url = self.setup.reference_link(ref)
        if url:
            return f"[{ref}]({url})"
        return ref


class ChangelogGenerator(api.ChangelogGenerator):
    """
    Generator of ``CHANGELOG.md``, with each release under a ``##`` heading.
    """

    @property
    def ext(self) -> str:
        return ".md"

    @property
    def split_re(self) -> str:
        return r"\n## "

    @property
    def intro_text(self):
        return (
            super().intro_text
            + " See [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) "
            "and [COMMITS.md](COMMITS.md) for commit guidelines."
        )

    @property
    def formatter(self):
        return FileUpdate

    def main_heading(self, caption: str) -> List[str]:
        return [f"# {caption}", ""]

    def para(self, text: str) -> List[str]:
        return [text, ""]
