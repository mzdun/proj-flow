# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.release** performs a relase on the hosting service.
"""

import typing
from typing import Iterable, Optional, Union

from proj_flow import api
from proj_flow.api import env
from proj_flow.base import registry
from proj_flow.log import commit, fmt, rich_text
from proj_flow.log.error import NoProjectError, VersionNotAdvancing

OneOrMoreStrings = Union[str, Iterable[str]]


class VersionUpdater:
    def on_version_change(self, _new_version: str) -> Optional[OneOrMoreStrings]:
        return None

    def on_version_change_tags(
        self, new_version: str, _tags: list[str]
    ) -> Optional[OneOrMoreStrings]:
        return self.on_version_change(new_version)


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


def _get_tags(rt: env.Runtime, git: commit.Git):
    tags = git.tag_list(silent=True)
    prev_tag = tags[-1] if len(tags) > 0 else None

    rt.message("Tags:")
    for tag in reversed(tags):
        rt.message("  >", tag, "*" if tag == prev_tag else "")

    return tags, prev_tag


def _config_next_version(
    *,
    rt: env.Runtime,
    forced_level: typing.Optional[commit.Level],
    take_all: bool,
    git: commit.Git,
    hosting: commit.Hosting,
    project: api.release.Project,
    tags: typing.List[str],
    prev_tag: typing.Optional[str],
):
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

    return changelog, setup, next_version


def _files_to_commit(
    *,
    rt: env.Runtime,
    dbg_changelog: bool,
    suite: api.release.ProjectSuite,
    generator: rich_text.api.ChangelogGenerator,
    setup: commit.LogSetup,
    changelog: commit.ChangeLog,
    tags: typing.List[str],
    next_version: str,
):
    result: typing.List[str] = []

    if not dbg_changelog and rt.dry_run:
        result.append(generator.filename)
        version_path = suite.get_version_file_path(rt)
        if version_path:
            result.append(version_path)

        return result

    generator.update_changelog(changelog, setup, rt)
    result.append(generator.filename)

    suite.set_version(rt, next_version)
    version_path = suite.get_version_file_path(rt)
    if version_path:
        result.append(version_path)

    for updater in version_updaters.get():
        modified = updater.on_version_change_tags(next_version, tags)
        if modified is None:
            continue

        if isinstance(modified, str):
            result.append(modified)
        else:
            result.extend(modified)

    return result


def add_release(
    *,
    rt: env.Runtime,
    dbg_changelog: bool,
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

    tags, prev_tag = _get_tags(rt, git)
    changelog, setup, next_version = _config_next_version(
        rt=rt,
        forced_level=forced_level,
        take_all=take_all,
        git=git,
        hosting=hosting,
        project=project,
        tags=tags,
        prev_tag=prev_tag,
    )

    commit_message = f"release {next_version}"
    git.add_files(
        *_files_to_commit(
            rt=rt,
            dbg_changelog=dbg_changelog,
            suite=suite,
            generator=generator,
            setup=setup,
            changelog=changelog,
            tags=tags,
            next_version=next_version,
        )
    )
    git.commit(f"chore: {commit_message}{fmt.format_commit_message(changelog)}")
    git.annotated_tag(typing.cast(str, setup.curr_tag), commit_message)

    if hosting.is_active:
        info = hosting.add_release(changelog, setup, git, draft)
        if info.url:
            msg = "Visit draft at" if info.is_draft else "Visit release at"
            rt.message(msg, info.url, level=env.Msg.ALWAYS)

    return setup.curr_tag
