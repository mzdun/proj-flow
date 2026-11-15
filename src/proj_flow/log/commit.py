# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.commit** allows analysing the git commits for
changelog generation. It parses the Conventional Commits into
a :data:`ChangeLog`, wraps the git commands used by the release process in
:class:`Git` and defines the :class:`Hosting` interface, through which the
releases are published on hosting services found by :data:`hosting_factories`.
"""

import re
import secrets
import string
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple, Optional

from proj_flow.api import env
from proj_flow.base import registry

#: Line separating commits in the ``git log`` output parsed by
#: :meth:`Git.get_log`. Randomized, so no commit message can contain it by
#: accident.
COMMIT_SEP = "--{}".format(
    "".join(secrets.choice(string.ascii_letters + string.digits) for i in range(20))
)


def set_commit_sep(sep: str):
    """
    Replace the :data:`COMMIT_SEP`, e.g. to get repeatable ``git log`` calls
    in tests.

    :param sep: new commit separator
    """
    global COMMIT_SEP
    COMMIT_SEP = sep


class Section(NamedTuple):
    """
    Changelog section for a commit type.
    """

    #: Commit type, as found in the commit subject, or
    #: :data:`BREAKING_CHANGE`.
    key: str

    #: Header of the section in the changelog.
    header: str


class Level(Enum):
    """
    Importance of a change, deciding which part of the semantic version is
    bumped by the release.
    """

    #: Change, which does not require a new version.
    BENIGN = 0

    #: Bug fix, bumps the patch version.
    PATCH = 2

    #: New feature, bumps the minor version.
    FEATURE = 3

    #: Breaking change, bumps the major version.
    BREAKING = 4


#: Names accepted by ``github release --force`` for overriding the level
#: calculated from the git log.
FORCED_LEVEL: dict[str, Level] = {
    "patch": Level.PATCH,
    "fix": Level.PATCH,
    "minor": Level.FEATURE,
    "feat": Level.FEATURE,
    "feature": Level.FEATURE,
    "major": Level.BREAKING,
    "breaking": Level.BREAKING,
    "release": Level.BREAKING,
}

#: Pseudo-type used for breaking changes, which would otherwise be hidden from
#: the changelog.
BREAKING_CHANGE = "BREAKING_CHANGE"

#: Main changelog sections, listed before any other section, in this order.
TYPES = [
    Section(BREAKING_CHANGE, "Breaking"),
    Section("feat", "New Features"),
    Section("fix", "Bug Fixes"),
]

#: Commit types, which are always visible in the changelog.
KNOWN_TYPES = [section.key for section in TYPES]

#: Commit types counted as other types. The original type becomes the scope of
#: the change, e.g. ``docs: ...`` is listed as a ``fix(docs): ...``.
TYPE_FIX = {"docs": "fix"}

#: Headers of the remaining changelog sections, visible with ``--all`` or
#: ``--with``. Types missing here use the type name as the header.
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
#: Commit footers recognized as issue references, mapped to the key used in
#: :attr:`Link.references`.
ISSUE_LINKS = {"refs": "references", "closes": "closes", "fixes": "fixes"}


class Link(NamedTuple):
    """
    Single changelog entry, extracted from a commit.
    """

    #: Scope of the change, from ``type(scope): summary``; may be empty.
    scope: str

    #: Summary of the change, from the commit subject.
    summary: str

    #: Full hash of the commit.
    hash: str

    #: Abbreviated hash of the commit.
    short_hash: str

    #: Change is breaking, either by ``!`` after the type or by
    #: a ``BREAKING CHANGE`` paragraph.
    is_breaking: bool

    #: Paragraphs of the ``BREAKING CHANGE`` description, if any.
    breaking_message: list[str]

    #: Issue references from the commit footers, keyed by the values of
    #: :data:`ISSUE_LINKS`.
    references: dict[str, list[str]]


class Commit(NamedTuple):
    """
    Parsed Conventional Commit.
    """

    #: Type of the commit, e.g. ``feat`` or ``fix``.
    type: str

    #: Changelog entry for the commit.
    link: Link


#: Changelog entries grouped by the commit type (or :data:`BREAKING_CHANGE`).
ChangeLog = dict[str, list[Link]]


def read_tag_date(tag: str, rt: env.Runtime):
    """
    Get the date of the commit a tag points to, falling back to today's date,
    if the tag is not found.

    :param tag: tag (or any other ref) to read the date of
    :param rt: runtime to run git with
    :returns: date in ``YYYY-MM-DD`` format
    """
    proc = rt.capture("git", "log", "-n1", "--format=%aI", tag)
    if proc.returncode != 0:
        return time.strftime("%Y-%m-%d")
    return proc.stdout.split("T", 1)[0]


def _get_commit(hash: str, short_hash: str, message: str) -> Optional[Commit]:
    subject, body = (message + "\n\n").split("\n\n", 1)
    split = subject.split(": ", 1)
    if len(split) != 2:
        return None

    encoded, summary = split
    encoded = encoded.strip()
    is_breaking = len(encoded) > 0 and encoded[-1] == "!"
    if is_breaking:
        encoded = encoded[:-1].rstrip()
    type_scope = encoded.split("(", 1)
    if not len(type_scope[0]):
        return None
    scope = ""
    if len(type_scope) == 2:
        scope = ")".join(type_scope[1].split(")")[:-1]).strip()

    references = {}
    lines = body.rstrip().split("\n")
    for indexPlus1 in range(len(lines), 0, -1):
        index = indexPlus1 - 1
        footerLine = lines[index].strip()
        if footerLine == "":
            lines = lines[:-1]
            continue
        footer = footerLine.split(": ", 1)
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

    breaking_change = None
    body = "\n".join(lines).strip().split("BREAKING CHANGE", 1)
    if (
        len(body) > 1
        and (len(body[0]) == 0 or body[0][-1:] == "\n")
        and (len(body[1]) == 1 or body[1][:1] == ":")
    ):
        body = body[1].lstrip(":").strip()
        breaking_change = [
            re.sub(r"\s+", " ", para.strip()) for para in body.split("\n\n")
        ]
        is_breaking = True

    return Commit(
        type_scope[0].strip(),
        Link(
            scope,
            summary,
            hash,
            short_hash,
            is_breaking,
            breaking_change or [],
            references,
        ),
    )


def _level_from_commit(commit: Commit) -> tuple[Level, str]:
    if commit.link.is_breaking:
        return (Level.BREAKING, commit.link.scope)
    try:
        currentType = TYPE_FIX[commit.type]
        currentScope = commit.type
    except KeyError:
        currentType = commit.type
        currentScope = commit.link.scope
    currentLevel = {"feat": Level.FEATURE, "fix": Level.PATCH}.get(
        currentType, Level.BENIGN
    )
    return (currentLevel, currentScope)


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
    """
    Release, as known to the hosting service. Hosting implementations may
    extend it with their own data.
    """

    #: Web page of the release.
    url: Optional[str] = None

    #: Release is still a draft.
    is_draft: Optional[bool] = None

    #: Name of the release.
    ref: Optional[str] = None

    #: Tag the release is attached to.
    tag: Optional[str] = None


class Hosting(ABC):
    """
    Generates links to the hosting service and manages the releases there.

    :param host_link: project link to hosting service
    """

    #: Project link to hosting service.
    host_link: str

    @property
    def is_active(self) -> bool:
        """Can publish a release"""
        return True

    def __init__(self, host_link: str):
        self.host_link = host_link

    @abstractmethod
    def single_commit_link(self, link: Link) -> Optional[str]:
        """
        Link to a single commit on this hosting platform.

        :param link: changelog entry of the commit
        :returns: URL of the commit, if the platform supports it
        """
        ...

    @abstractmethod
    def commit_listing_link(self, setup: "LogSetup") -> Optional[str]:
        """
        Link to a comparison page between two tags on this hosting platform.

        :param setup: log setup with the tags to compare
        :returns: URL of the comparison, if the platform supports it
        """
        ...

    @abstractmethod
    def reference_link(self, ref: str) -> Optional[str]:
        """
        Link to an issue, based on a reference, provided this hosting platform
        can recognize it.

        :param ref: issue reference, as written in a commit footer
        :returns: URL of the issue, if the reference is recognized
        """
        ...

    @abstractmethod
    def add_release(
        self,
        log: ChangeLog,
        setup: "LogSetup",
        git: "Git",
        draft: bool,
    ) -> ReleaseInfo:
        """
        Push the release commit and tag created for current setup, then create
        a release for the tag, putting the log into release notes.

        :param log: changes to put into the release notes
        :param setup: log setup, with :attr:`LogSetup.curr_tag` naming the
            new release
        :param git: git wrapper to push the release with
        :param draft: create the release as a draft
        :returns: information about the created release
        """
        ...

    @abstractmethod
    def locate_release(self, release_name: str) -> Optional[ReleaseInfo]:
        """
        Locate a release by its name.

        :param release_name: name of the release, usually the version tag
        :returns: information about the release, if found
        """
        ...

    @abstractmethod
    def upload_to_release(
        self,
        release: ReleaseInfo,
        directory: str,
        names: list[str],
    ) -> None:
        """
        Upload package artifacts to the release, replacing any artifacts with
        the same names.

        :param release: release to upload to
        :param directory: directory the artifacts are in
        :param names: file names of the artifacts, relative to ``directory``
        """
        ...

    @abstractmethod
    def publish(self, release: ReleaseInfo) -> ReleaseInfo:
        """
        Publish given release, return updated release info.

        :param release: draft release to publish
        :returns: information about the published release
        """
        ...

    def delete_release(self, release: ReleaseInfo) -> bool:
        """
        Remove given release (draft or not) from hosting. Does not touch the
        underlying tag. The default implementation removes nothing.

        :param release: release to remove
        :returns: ``True``, if the release was removed
        """
        return False


class NoHosting(Hosting):
    """
    Stands in for a hosting service, when none is found among the git remotes.
    It is never active, generates no links and creates no releases.
    """

    @property
    def is_active(self) -> bool:
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

    def locate_release(self, release_name: str) -> Optional[ReleaseInfo]:
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
    Represents setup for log extraction.
    """

    #: Generate links to the hosting service.
    hosting: Hosting

    #: Start of commit range. If missing, represent the start of current branch.
    prev_tag: Optional[str]

    #: End of commit range. If missing, represent the HEAD of current branch.
    curr_tag: Optional[str]

    #: Refs and ranges of commits to hide in the generated changelog
    omit: list[str]

    #: Allow reacting to commits with typos in scope names
    scope_fix: dict[str, str] = field(default_factory=dict)

    #: Choose either all Conventional Commits or only ``feat``/``fix`` ones.
    take_all: bool = False

    #: If not taking all, which commits still should be included in addition to ``feat``/``fix`` ones.
    with_types: list[str] = field(default_factory=list)

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
        """
        Link to a single commit on hosting platform attached to this setup.

        :param link: changelog entry of the commit
        """
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

        :param ref: issue reference, as written in a commit footer
        """
        return self.hosting.reference_link(ref)


class Remote(NamedTuple):
    """
    Single line of ``git remote -v`` output.
    """

    #: Name of the remote, e.g. ``origin``.
    name: str

    #: Either ``fetch`` or ``push``.
    usage: str

    #: URL of the remote.
    url: str


class Git:
    """
    Runs the git commands needed by the changelog and release process.
    Commands changing the repository are printed and skipped with
    ``--dry-run``; read-only queries always run.

    :param rt: runtime to run git with
    """

    #: Runtime to run git with.
    rt: env.Runtime

    def __init__(self, rt: env.Runtime):
        self.rt = rt

    def get_log(self, setup: LogSetup, silent=False) -> tuple[ChangeLog, Level]:
        """
        Read the changes from the commit range of the setup.

        :param setup: log setup with the commit range and filters
        :param silent: do not print the git commands
        :returns: changelog of visible changes and the highest level of all
            changes, visible or not
        """
        omit = set[str]()
        args = ["git", "log", f"--format=%H"]
        for ref in setup.omit:
            stdout = set(
                self.rt.capture(*args, ref, silent=silent).stdout.strip().split("\n")
            )
            omit = omit.union(stdout)

        args = ["git", "log", f"--format=%h %H%n%B%n{COMMIT_SEP}"]

        commit_range = setup.commit_range
        if commit_range:
            args.append(commit_range)

        proc = self.rt.capture(*args, silent=silent)
        return self.parse_log(proc.stdout, COMMIT_SEP, setup, omit)

    def parse_log(
        self, git_log_output: str, separator: str, setup: LogSetup, omit: set[str]
    ):
        """
        Parse the output of ``git log --format=%h %H%n%B%n<separator>``.
        Release commits and commits with ``(no-log)`` in summary are always
        skipped, other hidden types only appear with
        :attr:`LogSetup.take_all`, unless they are breaking.

        :param git_log_output: output of ``git log`` to parse
        :param separator: line separating the commits
        :param setup: log setup with visibility filters and scope fixes
        :param omit: full hashes of commits to leave out
        :returns: changelog of visible changes and the highest level of all
            changes, visible or not
        """
        commitLog: list[Commit] = []
        amassed: list[str] = []
        for line in git_log_output.split("\n"):
            if line == separator:
                if len(amassed):
                    short_hash, hash = amassed[0].split(" ")
                    if hash in omit:
                        amassed = []
                        continue
                    commit = _get_commit(
                        hash, short_hash, "\n".join(amassed[1:]).strip()
                    )
                    amassed = []

                    if commit is None:
                        continue

                    commitLog.append(commit)
                continue
            amassed.append(line)

        changes: ChangeLog = {}
        level = Level.BENIGN

        for commit in commitLog:
            link = commit.link

            # Hide even from --all
            if commit.type == "chore" and link.summary[:8] == "release ":
                continue
            if "(no-log)" in link.summary:
                continue

            current_level, current_scope = _level_from_commit(commit)
            if current_level.value > level.value:
                level = current_level
            current_type = TYPE_FIX.get(commit.type, commit.type)
            hidden = (
                current_type not in KNOWN_TYPES and current_type not in setup.with_types
            )

            if hidden and not link.is_breaking and not setup.take_all:
                continue
            if hidden and link.is_breaking:
                current_type = BREAKING_CHANGE

            current_scope = setup.scope_fix.get(current_scope, current_scope)
            if current_type not in changes:
                changes[current_type] = []
            changes[current_type].append(
                Link(
                    current_scope,
                    link.summary,
                    link.hash,
                    link.short_hash,
                    link.is_breaking,
                    link.breaking_message,
                    link.references,
                )
            )

        return changes, level

    def remotes(self, silent=False):
        """
        Enumerate the remotes of the repository.

        :param silent: do not print the git command
        :returns: generator of :class:`Remote` entries, one for each name and
            usage
        """
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
        """
        Get list of version tags, in increasing order. Only tags in form of
        ``v<semver>`` are listed and pre-releases come before their release.

        :param silent: do not print the git command
        """
        tags: list[str] = self.rt.capture("git", "tag", silent=silent).stdout.split(
            "\n"
        )
        versions: list[tuple[tuple[int, int, int, str], str]] = []
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

    def cmd(self, *command: str) -> None:
        """
        Run a git command, which changes the repository. The command is
        skipped with ``--dry-run``.

        :param command: git subcommand with its arguments
        :raises StepFailed: the command has failed
        """
        self.rt.cmd("git", *command)

    def add_files(self, *files: str):
        """
        Stage the files for the next commit.

        :param files: paths of the files to stage
        """
        self.cmd("add", *files)

    def commit(self, message: str):
        """
        Commit the staged files.

        :param message: full commit message
        """
        self.cmd("commit", "-m", message)

    def annotated_tag(self, new_tag: str, message: str):
        """
        Attach an annotated tag to HEAD.

        :param new_tag: name of the tag
        :param message: message of the tag
        """
        self.cmd("tag", "-am", message, new_tag)

    def push_with_refs(self, remote: str, branch: str):
        """
        Push the branch with its annotated tags, with lease.

        :param remote: name of the remote to push to
        :param branch: branch to push
        """
        self.cmd("push", remote, branch, "--follow-tags", "--force-with-lease")

    def head_commit(self) -> tuple[str, str]:
        """
        Get hash and subject line of the HEAD commit.

        :returns: full hash and subject, or two empty strings, if there is no
            HEAD commit
        """
        proc = self.rt.capture("git", "log", "-1", "--format=%H%n%s", silent=True)
        lines = proc.stdout.strip().split("\n", 1)
        if proc.returncode != 0 or len(lines) != 2:
            return "", ""
        return lines[0], lines[1]

    def tags_at(self, ref: str) -> list[str]:
        """
        Get list of tags pointing at given ref.

        :param ref: commit, branch or any other ref to check
        """
        proc = self.rt.capture("git", "tag", "--points-at", ref, silent=True)
        return [tag for tag in proc.stdout.split("\n") if tag]

    def delete_tag(self, tag: str):
        """
        Delete local tag.

        :param tag: name of the tag
        """
        self.cmd("tag", "-d", tag)

    def delete_remote_tag(self, remote: str, tag: str):
        """
        Delete tag from given remote.

        :param remote: name of the remote
        :param tag: name of the tag
        """
        self.cmd("push", remote, "--delete", f"refs/tags/{tag}")

    def reset_keep(self, ref: str):
        """
        Move current branch to given ref with ``git reset --keep``. Files,
        which differ between HEAD and the ref are brought back to their state
        at the ref, while local changes to other files are kept. The reset
        is aborted, if any of the files to be reverted has local changes.

        :param ref: commit to move the branch to
        """
        self.cmd("reset", "--keep", ref)

    def push_with_lease(self, remote: str, branch: str, expected: str):
        """
        Force-push HEAD to the branch on given remote, but only if the remote
        branch still points at the ``expected`` commit.

        :param remote: name of the remote
        :param branch: name of the remote branch to update
        :param expected: full hash the remote branch must still point at
        """
        self.cmd(
            "push",
            remote,
            f"HEAD:refs/heads/{branch}",
            f"--force-with-lease=refs/heads/{branch}:{expected}",
        )


class HostingFactory(ABC):
    """
    Extension point for hosting services, registered with
    :data:`hosting_factories`.
    """

    @abstractmethod
    def from_repo(self, git: Git, remote: Optional[str] = None) -> Optional[Hosting]:
        """
        Create the hosting for the repository, if any of its remotes points to
        this service.

        :param git: git wrapper to read the remotes with
        :param remote: name of the remote to prefer
        :returns: the hosting, or ``None`` if the repository is not hosted
            there
        """
        ...


#: Registry of known hosting services.
hosting_factories = registry.Registry[HostingFactory]("HostingFactory")
