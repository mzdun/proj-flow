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
    def __init__(self, setup: commit.LogSetup, commit_date: str):
        super().__init__(setup, commit_date)

    def intro_lines(self) -> List[str]:
        version = (self.setup.curr_tag or " *unknown*")[1:]
        compare = self.setup.commit_listing_link()

        if compare:
            heading = f"`{version} <{compare}>`_ ({self.commit_date})"
        else:
            heading = f"{version}"

        return [
            heading,
            "=" * len(heading),
            "",
        ]

    def section_header(self, lines: List[str], header):
        lines.extend([header, "-" * len(header), ""])

    def summary(self, text: str) -> str:
        return text.replace("`", "``")

    def outro_lines(self, _: List[str]) -> None:
        pass

    def short_hash_link(self, link: commit.Link):
        url = self.setup.single_commit_link(link)
        if not url:
            return link.short_hash
        return f"`{link.short_hash} <{url}>`_"


class ChangelogGenerator(api.ChangelogGenerator):
    @property
    def ext(self):
        return ".rst"

    @property
    def split_re(self):
        return r"\n`[0-9]+\.[0-9]+[^>]+\>`\_ \([^)]+\)\n==+\n"

    @property
    def formatter(self):
        return FileUpdate

    def main_heading(self, caption: str) -> List[str]:
        line = "=" * len(caption)
        return [line, caption, line, ""]

    def para(self, text: str) -> List[str]:
        return [msg.CommitMessage.wrap_at_78(text), ""]
