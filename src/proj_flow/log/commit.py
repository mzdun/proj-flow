# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.commit** allows analysing the git commits for
changelog generation.
"""

import re
import secrets
import string
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, NamedTuple, Optional, Tuple

from proj_flow.api import env
from proj_flow.base import registry

COMMIT_SEP = f"--{''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(20))}"


def set_commit_sep(sep: str):
    global COMMIT_SEP
    COMMIT_SEP = sep


class Section(NamedTuple):
    key: str
    header: str


class Level(Enum):
    BENIGN = 0
    PATCH = 2
    FEATURE = 3
    BREAKING = 4


FORCED_LEVEL: Dict[str, Level] = {
    "patch": Level.PATCH,
    "fix": Level.PATCH,
    "minor": Level.FEATURE,
    "feat": Level.FEATURE,
    "feature": Level.FEATURE,
    "major": Level.BREAKING,
    "breaking": Level.BREAKING,
    "release": Level.BREAKING,
}

BREAKING_CHANGE = "BREAKING_CHANGE"
TYPES = [
    Section(BREAKING_CHANGE, "Breaking"),
    Section("feat", "New Features"),
    Section("fix", "Bug Fixes"),
]
KNOWN_TYPES = [section.key for section in TYPES]
TYPE_FIX = {"docs": "fix"}
ALL_TYPES = {
    "assets": "Assets",
    "build": "Build System",
    "chore": "Chores",
    "ci": "Continuous Integration",
    "perf": "Performance Improvements",
    "refactor": "Code Refactoring",
    "revert": "Reverts",
    "style": "Code Style",
    "test": "Tests",
}
ISSUE_LINKS = {"refs": "references", "closes": "closes", "fixes": "fixes"}


class Link(NamedTuple):
    scope: str
    summary: str
    hash: str
    short_hash: str
    is_breaking: bool
    breaking_message: List[str]
    references: Dict[str, List[str]]


class Commit(NamedTuple):
    type: str
    link: Link


ChangeLog = Dict[str, List[Link]]


def read_tag_date(tag: str, rt: env.Runtime):
    proc = rt.capture("git", "log", "-n1", "--format=%aI", tag)
    if proc.returncode != 0:
        return time.strftime("%Y-%m-%d")
    return proc.stdout.split("T", 1)[0]


def _get_commit(long_hash: str, short_hash: str, message: str) -> Optional[Commit]:
    subject, body_text = (message + "\n\n").split("\n\n", 1)
    split = subject.split(": ", 1)
    if len(split) != 2:
        return None

    encoded, summary = split
    encoded = encoded.strip()
    is_breaking = len(encoded) > 0 and encoded[-1] == "!"
    if is_breaking:
        encoded = encoded[:-1].rstrip()
    type_scope = encoded.split("(", 1)
    if not type_scope[0]:
        return None
    scope = ""
    if len(type_scope) == 2:
        scope = ")".join(type_scope[1].split(")")[:-1]).strip()

    body_text = body_text.rstrip()
    references = _get_references(body_text)
    breaking_change, is_breaking = _get_breaking_change_footer(body_text, is_breaking)

    return Commit(
        type_scope[0].strip(),
        Link(
            scope,
            summary,
            long_hash,
            short_hash,
            is_breaking,
            breaking_change or [],
            references,
        ),
    )


def _get_references(body_text: str):
    lines = body_text.split("\n")

    references: Dict[str, List[str]] = {}

    for index_plus_1 in range(len(lines), 0, -1):
        index = index_plus_1 - 1
        footer_line = lines[index].strip()
        if footer_line == "":
            lines = lines[:-1]
            continue
        footer = footer_line.split(": ", 1)
        if len(footer) == 1:
            break
        lines = lines[:-1]
        name = footer[0].strip().lower()
        if name in ISSUE_LINKS:
            items = [v.strip() for v in footer[1].split(",")]
            key = ISSUE_LINKS[name]
            if key not in references:
                references[key] = []
            references[key] = items + references[key]
            continue

    return references


def _get_breaking_change_footer(body_text: str, is_breaking: bool):
    breaking_change: Optional[List[str]] = None
    body_br = body_text.strip().split("BREAKING CHANGE", 1)
    if (
        len(body_br) > 1
        and (len(body_br[0]) == 0 or body_br[0][-1:] == "\n")
        and (len(body_br[1]) == 1 or body_br[1][:1] == ":")
    ):
        breaking_change_text = body_br[1].lstrip(":").strip()
        breaking_change = [
            re.sub(r"\s+", " ", para.strip())
            for para in breaking_change_text.split("\n\n")
        ]
        is_breaking = True

    return breaking_change, is_breaking


def _level_from_commit(commit: Commit) -> Tuple[Level, str]:
    if commit.link.is_breaking:
        return (Level.BREAKING, commit.link.scope)
    try:
        current_type = TYPE_FIX[commit.type]
        current_scope = commit.type
    except KeyError:
        current_type = commit.type
        current_scope = commit.link.scope
    current_level = {"feat": Level.FEATURE, "fix": Level.PATCH}.get(
        current_type, Level.BENIGN
    )
    return current_level, current_scope


def _sem_ver(tag: str):
    split = tag.split("-", 1)
    if len(split) == 2:
        stability = split[1]
    else:
        stability = ""
    ver = [int(s) for s in split[0].split(".")]
    while len(ver) < 3:
        ver.append(0)
    return [*ver, stability]


@dataclass
class ReleaseInfo:
    url: Optional[str] = None
    is_draft: Optional[bool] = None
    ref: Optional[str] = None
    tag: Optional[str] = None


class Hosting(ABC):
    """
    Generates links to the hosting service.
    """

    #: Project link to hosting service.
    host_link: str

    @property
    def is_active(self):
        """Can publish a release"""
        return True

    def __init__(self, host_link: str):
        self.host_link = host_link

    @abstractmethod
    def single_commit_link(self, link: Link) -> Optional[str]:
        """Link to a single commit on this hosting platform."""

    @abstractmethod
    def commit_listing_link(self, setup: "LogSetup") -> Optional[str]:
        """
        Link to a comparison page between two tags on this hosting platform.
        """

    @abstractmethod
    def reference_link(self, ref: str) -> Optional[str]:
        """
        Link to an issue, based on a reference, provided this hosting platform
        can recognize it.
        """

    @abstractmethod
    def add_release(
        self,
        log: ChangeLog,
        setup: "LogSetup",
        git: "Git",
        draft: bool,
    ) -> ReleaseInfo:
        """
        Publish a release for current setup, putting the log into release
        notes.
        """

    @abstractmethod
    def locate_release(self, release_name: str) -> Optional[ReleaseInfo]:
        """
        Locate a release by its name.
        """

    @abstractmethod
    def upload_to_release(
        self,
        release: ReleaseInfo,
        directory: str,
        names: list[str],
    ):
        """
        Upload package artifacts to the release.
        """

    @abstractmethod
    def publish(self, release: ReleaseInfo) -> ReleaseInfo:
        """
        Publish given release, return updated release info.
        """


class NoHosting(Hosting):
    """
    Generates links to the hosting service.
    """

    @property
    def is_active(self):
        return False

    def __init__(self):
        super().__init__("")

    def single_commit_link(self, link: Link) -> Optional[str]:
        return None

    def commit_listing_link(self, setup: "LogSetup") -> Optional[str]:
        return None

    def reference_link(self, ref: str) -> Optional[str]:
        return None

    def add_release(
        self, log: ChangeLog, setup: "LogSetup", git: "Git", draft: bool
    ) -> ReleaseInfo:
        return ReleaseInfo(is_draft=False)

    def locate_release(self, _release_name: str) -> Optional[ReleaseInfo]:
        return None

    def upload_to_release(
        self,
        release: ReleaseInfo,
        directory: str,
        names: list[str],
    ):
        return None

    def publish(self, release: ReleaseInfo):
        return ReleaseInfo(is_draft=False)


@dataclass
class LogSetup:
    """
    Represents setup for log extarction.
    """

    #: Generate links to the hosting service.
    hosting: Hosting

    #: Start of commit range. If missing, represent the start of current branch.
    prev_tag: Optional[str]

    #: End of commit range. If missing, represent the HEAD of current branch.
    curr_tag: Optional[str]

    #: Allow reacting to commits with typos in scope names
    scope_fix: Dict[str, str] = field(default_factory=dict)

    #: Choose either all Conventional Commits or only ``feat``/``fix`` ones.
    take_all: bool = False

    @property
    def commit_range(self):
        """Commit range for log retrieval."""

        if self.prev_tag is None:
            if self.curr_tag is None:
                return None
            return self.curr_tag

        if self.curr_tag is None:
            return f"{self.prev_tag}..HEAD"

        return f"{self.prev_tag}..{self.curr_tag}"

    def single_commit_link(self, link: Link):
        """Link to a single commit on hosting platform attached to this setup."""
        return self.hosting.single_commit_link(link)

    def commit_listing_link(self):
        """
        Link to a comparison page between two tags on hosting platform
        attached to this setup.
        """
        return self.hosting.commit_listing_link(self)

    def reference_link(self, ref: str):
        """
        Link to an issue, based on a reference, provided hosting platform
        attached to this setup can recognize it.
        """
        return self.hosting.reference_link(ref)


class Remote(NamedTuple):
    name: str
    usage: str
    url: str


class Git:
    rt: env.Runtime

    def __init__(self, rt: env.Runtime):
        self.rt = rt

    def get_log(self, setup: LogSetup, silent=False) -> Tuple[ChangeLog, Level]:
        args = ["git", "log", f"--format=%h %H%n%B%n{COMMIT_SEP}"]

        commit_range = setup.commit_range
        if commit_range:
            args.append(commit_range)

        proc = self.rt.capture(*args, silent=silent)
        return self.parse_log(proc.stdout, COMMIT_SEP, setup)

    def parse_log(self, git_log_output: str, separator: str, setup: LogSetup):
        commit_log: List[Commit] = []
        amassed: List[str] = []
        for line in git_log_output.split("\n"):
            if line == separator:
                if amassed:
                    short_hash, long_hash = amassed[0].split(" ")
                    commit = _get_commit(
                        long_hash, short_hash, "\n".join(amassed[1:]).strip()
                    )
                    amassed = []

                    if commit is None:
                        continue

                    commit_log.append(commit)
                continue
            amassed.append(line)

        changes: ChangeLog = {}
        level = Level.BENIGN

        for commit in commit_log:
            link, level, current_type = Git._get_link(setup, commit, level)
            if not link:
                continue

            if current_type not in changes:
                changes[current_type] = []
            changes[current_type].append(link)

        return changes, level

    @staticmethod
    def _get_link(
        setup: LogSetup, commit: Commit, level: Level
    ) -> Tuple[Optional[Link], Level, str]:
        link = commit.link

        # Hide even from --all
        if commit.type == "chore" and link.summary[:8] == "release ":
            return None, level, ""

        if "(no-log)" in link.summary:
            return None, level, ""

        current_level, current_scope = _level_from_commit(commit)
        if current_level.value > level.value:
            level = current_level
        current_type = TYPE_FIX.get(commit.type, commit.type)
        hidden = current_type not in KNOWN_TYPES

        if hidden and not link.is_breaking and not setup.take_all:
            return None, level, ""

        if hidden and link.is_breaking:
            current_type = BREAKING_CHANGE

        current_scope = setup.scope_fix.get(current_scope, current_scope)

        result = Link(
            current_scope,
            link.summary,
            link.hash,
            link.short_hash,
            link.is_breaking,
            link.breaking_message,
            link.references,
        )
        return result, level, current_type

    def remotes(self, silent=False):
        remotes = self.rt.capture("git", "remote", "-v", silent=silent).stdout.split(
            "\n"
        )
        for line in remotes:
            split = line.split("\t", 1)
            if len(split) != 2:
                continue

            remote_name, remote_url_use = split
            remote_use = ""
            remote_url = None
            for use in ["fetch", "push"]:
                suffix = f" ({use})"
                if remote_url_use.endswith(suffix):
                    remote_url = remote_url_use[: -len(suffix)].strip()
                    remote_use = use
                    break

            if remote_url is None:
                continue

            yield Remote(remote_name, remote_use, remote_url)

    def tag_list(self, silent=False):
        """Get list of version tags, in increasing order."""
        tags: List[str] = self.rt.capture("git", "tag", silent=silent).stdout.split(
            "\n"
        )
        versions: List[Tuple[Tuple[int, int, int, str], str]] = []
        for tag in tags:
            if tag[:1] != "v":
                continue
            try:
                value = _sem_ver(tag[1:])
                if value[3] == "":
                    value[3] = "z"
                versions.append(((*value,), tag))
            except Exception:
                continue

        versions.sort()
        return list(map(lambda pair: pair[1], versions))

    def current_branch(self):
        """Get currently checked-out branch"""
        return self.rt.capture("git", "branch", "--show-current").stdout.strip()

    def cmd(self, *command: str):
        return self.rt.cmd("git", *command)

    def add_files(self, *files: str):
        return self.cmd("add", *files)

    def commit(self, message: str):
        return self.cmd("commit", "-m", message)

    def annotated_tag(self, new_tag: str, message: str):
        return self.cmd("tag", "-am", message, new_tag)

    def push_with_refs(self, remote: str, branch: str):
        return self.cmd("push", remote, branch, "--follow-tags", "--force-with-lease")


class HostingFactory(ABC):
    @abstractmethod
    def from_repo(
        self, git: Git, remote: Optional[str] = None
    ) -> Optional[Hosting]: ...


hosting_factories = registry.Registry[HostingFactory]("HostingFactory")
