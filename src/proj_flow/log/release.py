# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.release** performs a relase on the hosting service.
"""

import typing
from abc import ABC, abstractmethod
from typing import Iterable, Union

from proj_flow import api
from proj_flow.api import env
from proj_flow.base import registry
from proj_flow.log import commit, fmt, rich_text
from proj_flow.log.error import NoProjectError, VersionNotAdvancing

OneOrMoreStrings = Union[str, Iterable[str]]


class VersionUpdater(ABC):
    @abstractmethod
    def on_version_change(self, new_version: str) -> OneOrMoreStrings: ...


version_updaters = registry.Registry[VersionUpdater]("VersionUpdater")


def _bump_version(ver: str, level: commit.Level):
    split = ver.split("-", 1)
    if len(split) == 2:
        stability = f"-{split[1]}"
    else:
        stability = ""

    semver = [int(s) for s in split[0].split(".")]
    while len(semver) < 3:
        semver.append(0)
    semver = semver[:3]

    if level.value > commit.Level.BENIGN.value:
        # This turns [1, 2, 3] through 4 - x into [3, 2, 1]
        lvl = commit.Level.BREAKING.value - level.value
        semver[lvl] += 1
        for index in range(lvl + 1, len(semver)):
            semver[index] = 0

    return ".".join(str(v) for v in semver) + stability


def _get_project(rt: env.Runtime):
    def wrap(suite: api.release.ProjectSuite):
        return suite.get_project(rt)

    return wrap


def add_release(
    rt: env.Runtime,
    forced_level: typing.Optional[commit.Level],
    take_all: bool,
    draft: bool,
    generator: rich_text.api.ChangelogGenerator,
    git: commit.Git,
    hosting: commit.Hosting,
):
    """
    Bumps the project version based on current git logs, creates a "chore"
    commit for the change, attaches an annotated tag with the version number
    and pushes it all to hosting.
    """

    suite, project = api.release.project_suites.find(_get_project(rt))

    if not project or not suite:
        raise NoProjectError()

    tags = git.tag_list(silent=True)

    prev_tag = tags[-1] if len(tags) > 0 else None

    rt.message("Tags:")
    for tag in reversed(tags):
        rt.message("  >", tag, "*" if tag == prev_tag else "")

    setup = commit.LogSetup(hosting, prev_tag, None, take_all=take_all)
    changelog, log_level = git.get_log(setup)

    rt.message("Changelog:")
    for grp, links in changelog.items():
        rt.message("  >", grp)
        for link in links:
            rt.message("     ", str(link.summary))

    project_version = f"{project.version}"
    next_version = _bump_version(project_version, forced_level or log_level)
    setup.curr_tag = f"v{next_version}"

    if next_version == project_version:
        raise VersionNotAdvancing(next_version)

    if setup.curr_tag in tags:
        rt.fatal(f"Tag {setup.curr_tag} already exists.")

    files_to_commit: typing.List[str] = []
    if not rt.dry_run:
        generator.update_changelog(changelog, setup, rt)
        files_to_commit.append(generator.filename)

        suite.set_version(rt, next_version)
        version_path = suite.get_version_file_path(rt)
        if version_path:
            files_to_commit.append(version_path)

        for updater in version_updaters.get():
            modified = updater.on_version_change(next_version)
            if isinstance(modified, str):
                files_to_commit.append(modified)
            else:
                files_to_commit.extend(modified)
    else:
        files_to_commit.append(generator.filename)
        version_path = suite.get_version_file_path(rt)
        if version_path:
            files_to_commit.append(version_path)

    commit_message = f"release {next_version}"
    git.add_files(*files_to_commit)
    git.commit(f"chore: {commit_message}{fmt.format_commit_message(changelog)}")
    git.annotated_tag(setup.curr_tag, commit_message)

    if hosting.is_active:
        info = hosting.add_release(changelog, setup, git, draft)
        if info.url:
            msg = "Visit draft at" if info.is_draft else "Visit release at"
            rt.message(msg, info.url, level=env.Msg.ALWAYS)

    return setup.curr_tag
