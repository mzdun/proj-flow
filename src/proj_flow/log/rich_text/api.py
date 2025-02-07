# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.rich_text.api** defines base types for CHANGELOG.md
manipulation.
"""

import abc
import os
import re
from typing import Dict, List, Type

from proj_flow import base
from proj_flow.api import env
from proj_flow.log import commit, msg


class FileUpdate(msg.ReleaseMessage):
    commit_date: str

    def __init__(self, setup: commit.LogSetup, commit_date: str):
        super().__init__(setup)
        self.commit_date = commit_date


class ChangelogGenerator(abc.ABC):
    @property
    def filename(self) -> str:
        return f"CHANGELOG{self.ext}"

    @property
    @abc.abstractmethod
    def formatter(self) -> Type[FileUpdate]: ...

    @property
    @abc.abstractmethod
    def ext(self) -> str: ...

    @property
    @abc.abstractmethod
    def split_re(self) -> str: ...

    @property
    def intro_head(self) -> str:
        return "Changelog"

    @property
    def intro_text(self) -> str:
        return "All notable changes to this project will be documented in this file."

    @abc.abstractmethod
    def main_heading(self, caption: str) -> List[str]: ...

    @abc.abstractmethod
    def para(self, text: str) -> List[str]: ...

    def intro(self):
        lines = self.main_heading(self.intro_head)
        lines.extend(self.para(self.intro_text))
        return "\n".join(lines)

    def format_changelog(
        self, log: commit.ChangeLog, setup: commit.LogSetup, rt: env.Runtime
    ):
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
        scope_fix: Dict[str, str] = {},
        take_all: bool = False,
    ):
        prev_tag = None
        entire_log: List[str] = []
        for curr_tag in tags:
            setup = commit.LogSetup(
                links, prev_tag, curr_tag, scope_fix=scope_fix, take_all=take_all
            )
            log, _ = git.get_log(setup)
            text = self.format_changelog(log, setup, rt)
            prev_tag = curr_tag

            entire_log.append(text + "\n")

        entire_log.append(self.intro())

        filename = os.path.join(rt.root, f"CHANGELOG{self.ext}")
        with open(filename, "wb") as f:
            for text in reversed(entire_log):
                f.write(text.encode("UTF-8"))

    def update_changelog(
        self,
        log: commit.ChangeLog,
        setup: commit.LogSetup,
        rt: env.Runtime,
    ):
        formatter = self.formatter(
            setup, commit.read_tag_date(setup.curr_tag or "HEAD", rt)
        )
        text = formatter.format_changelog(log)
        filename = self.filename
        path = os.path.join(rt.root, filename)

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

        with open(filename, "wb") as f:
            f.write(new_text.encode("UTF-8"))


changelog_generators = base.registry.Registry[ChangelogGenerator]("ChangelogGenerator")
