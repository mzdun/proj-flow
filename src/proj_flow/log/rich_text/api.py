# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.rich_text.api** defines base types for CHANGELOG.md
manipulation.
"""

import abc
import os
import re
from typing import Dict, List, Optional, Type

from proj_flow import base
from proj_flow.api import env
from proj_flow.log import commit, msg


class FileUpdate(msg.ReleaseMessage):
    """
    New section of the changelog file, describing a release.

    :param setup: log setup of the release
    :param commit_date: date of the release, as ``YYYY-MM-DD``
    """

    commit_date: str

    def __init__(self, setup: commit.LogSetup, commit_date: str):
        super().__init__(setup)
        self.commit_date = commit_date


class ChangelogGenerator(abc.ABC):
    """
    Extension point for the changelog file format, registered with
    :data:`changelog_generators`.
    """

    @property
    def filename(self) -> str:
        """Name of the changelog file, ``CHANGELOG`` with the :attr:`ext`."""
        return f"CHANGELOG{self.ext}"

    @property
    @abc.abstractmethod
    def formatter(self) -> Type[FileUpdate]:
        """Class formatting a single release section of the file."""
        ...

    @property
    @abc.abstractmethod
    def ext(self) -> str:
        """Extension of the changelog file, with the leading dot."""
        ...

    @property
    @abc.abstractmethod
    def split_re(self) -> str:
        """
        Regular expression matching the heading of a release section. A new
        release is inserted before the first match.
        """
        ...

    @property
    def intro_head(self) -> str:
        """Main heading of the changelog file."""
        return "Changelog"

    @property
    def intro_text(self) -> str:
        """Paragraph under the main heading."""
        return "All notable changes to this project will be documented in this file."

    @abc.abstractmethod
    def main_heading(self, caption: str) -> List[str]:
        """
        Format the main heading of the file.

        :param caption: text of the heading
        :returns: lines of the heading
        """
        ...

    @abc.abstractmethod
    def para(self, text: str) -> List[str]:
        """
        Format a paragraph.

        :param text: text of the paragraph
        :returns: lines of the paragraph
        """
        ...

    def intro(self):
        """
        Text of a new, empty changelog file: main heading and intro
        paragraph.
        """
        lines = self.main_heading(self.intro_head)
        lines.extend(self.para(self.intro_text))
        return "\n".join(lines)

    def format_changelog(
        self, log: commit.ChangeLog, setup: commit.LogSetup, rt: env.Runtime
    ):
        """
        Format a release section, dated with the commit of the current tag
        (or HEAD).

        :param log: changes of the release
        :param setup: log setup of the release
        :param rt: runtime to read the tag date with
        :returns: text of the section
        """
        formatter = self.formatter(
            setup, commit.read_tag_date(setup.curr_tag or "HEAD", rt)
        )
        return formatter.format_changelog(log)

    def create_changelog(
        self,
        tags: List[str],
        git: commit.Git,
        links: commit.Hosting,
        rt: env.Runtime,
        scope_fix: Optional[Dict[str, str]] = None,
        take_all: bool = False,
    ):
        """
        Write the whole changelog file anew, with one section for each tag,
        newest first.

        :param tags: version tags, in increasing order
        :param git: git wrapper to read the logs with
        :param links: hosting to generate the links with
        :param rt: runtime with the project root
        :param scope_fix: scope names to replace, e.g. to fix typos
        :param take_all: put all Conventional Commits into the changelog
        """
        prev_tag = None
        entire_log: List[str] = []
        for curr_tag in tags:
            setup = commit.LogSetup(
                links,
                prev_tag,
                curr_tag,
                omit=[],
                scope_fix=scope_fix or {},
                take_all=take_all,
            )
            log, _ = git.get_log(setup)
            text = self.format_changelog(log, setup, rt)
            prev_tag = curr_tag

            entire_log.append(text + "\n")

        entire_log.append(self.intro())

        filename = rt.root / self.filename
        with open(filename, "wb") as f:
            for text in reversed(entire_log):
                f.write(text.encode("UTF-8"))

    def update_changelog(
        self,
        log: commit.ChangeLog,
        setup: commit.LogSetup,
        rt: env.Runtime,
    ):
        """
        Insert a new release section into the changelog file, before the
        previous release, as found by :attr:`split_re`. A missing file is
        created with the :meth:`intro`.

        :param log: changes of the release
        :param setup: log setup of the release
        :param rt: runtime with the project root
        """
        formatter = self.formatter(
            setup, commit.read_tag_date(setup.curr_tag or "HEAD", rt)
        )
        text = formatter.format_changelog(log)
        path = rt.root / self.filename

        try:
            with open(path, encoding="UTF-8") as f:
                changelog = f.read()
        except FileNotFoundError:
            changelog = self.intro()

        split = re.split(
            pattern=f"({self.split_re})",
            flags=re.MULTILINE,
            string=changelog,
            maxsplit=1,
        )
        new_text = split[0] + "\n" + text
        if len(split) > 1:
            new_text += "".join(split[1:])

        with open(path, "wb") as f:
            f.write(new_text.encode("UTF-8"))


#: Registry of changelog file formats.
changelog_generators = base.registry.Registry[ChangelogGenerator]("ChangelogGenerator")
