# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.log.release** performs a release on the hosting service, or
retracts the latest one. It also defines the :data:`version_updaters`
extension point for files, which need to follow the project version.
"""

import typing
from typing import Iterable, Optional, Union

from proj_flow import api
from proj_flow.api import env
from proj_flow.base import registry
from proj_flow.log import commit, fmt, rich_text
from proj_flow.log.error import NoProjectError, ReleaseError, VersionNotAdvancing

#: Single path or a list of paths.
OneOrMoreStrings = Union[str, Iterable[str]]


class VersionUpdater:
    """
    Extension point for updating additional files with the new version,
    registered with :data:`version_updaters`. Implementations override either
    of the methods; the files they modify are committed with the release.
    """

    def on_version_change(
        self, rt: env.Runtime, new_version: str
    ) -> Optional[OneOrMoreStrings]:
        """
        React to the version change. The default implementation does nothing.

        :param rt: runtime of the release
        :param new_version: version being released, without the ``v`` prefix
        :returns: path or paths of modified files, if any
        """
        return None

    def on_version_change_tags(
        self, rt: env.Runtime, new_version: str, tags: list[str]
    ) -> Optional[OneOrMoreStrings]:
        """
        React to the version change, knowing previous releases. The default
        implementation calls :meth:`on_version_change`.

        :param rt: runtime of the release
        :param new_version: version being released, without the ``v`` prefix
        :param tags: existing version tags, as returned by
            :meth:`Git.tag_list() <proj_flow.log.commit.Git.tag_list>`
        :returns: path or paths of modified files, if any
        """
        return self.on_version_change(rt, new_version)


#: Registry of additional version updaters.
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
    dbg_changelog: bool,
    forced_level: typing.Optional[commit.Level],
    take_all: bool,
    with_types: list[str],
    draft: bool,
    generator: rich_text.api.ChangelogGenerator,
    omit: list[str],
    git: commit.Git,
    hosting: commit.Hosting,
):
    """
    Bumps the project version based on current git logs, creates a "chore"
    commit for the change and attaches an annotated tag with the version
    number. If the hosting is active, its :meth:`Hosting.add_release()
    <proj_flow.log.commit.Hosting.add_release>` pushes the commit with the tag
    and creates the release; otherwise, nothing is pushed.

    With ``--dry-run`` (and no ``dbg_changelog``), the project files are not
    modified, while the git commands are only printed.

    :param rt: runtime of the release
    :param dbg_changelog: modify project files, changelog included, even with
        ``--dry-run``
    :param forced_level: use this level instead of one calculated from the
        log
    :param take_all: put all Conventional Commits into the changelog
    :param with_types: commit types to put into the changelog in addition to
        breaking changes, features and fixes
    :param draft: create the release on hosting as a draft
    :param generator: generator of the changelog file
    :param omit: refs and ranges of commits to hide in the changelog
    :param git: git wrapper for the repository
    :param hosting: hosting service to release on
    :returns: the new version tag
    :raises NoProjectError: no project suite recognizes the project
    :raises VersionNotAdvancing: no change since previous tag bumps the
        version
    """

    suite, project = api.release.project_suites.find(_get_project(rt))

    if not project or not suite:
        raise NoProjectError()

    tags = git.tag_list(silent=True)

    prev_tag = tags[-1] if len(tags) > 0 else None

    rt.message("Tags:")
    for tag in reversed(tags):
        rt.message("  >", tag, "*" if tag == prev_tag else "")

    setup = commit.LogSetup(
        hosting, prev_tag, None, omit=omit, take_all=take_all, with_types=with_types
    )
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
    if dbg_changelog or not rt.dry_run:
        generator.update_changelog(changelog, setup, rt)
        files_to_commit.append(generator.filename)

        suite.set_version(rt, next_version)
        version_path = suite.get_version_file_path(rt)
        if version_path:
            files_to_commit.append(version_path)

        for updater in version_updaters.get():
            modified = updater.on_version_change_tags(rt, next_version, tags)
            if modified is None:
                continue
            elif isinstance(modified, str):
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


#: Subject prefix of the commits created by :func:`add_release`.
RELEASE_SUBJECT_PREFIX = "chore: release "


def retract_release(
    rt: env.Runtime,
    git: commit.Git,
    hosting: commit.Hosting,
    remote: typing.Optional[str],
    force: bool = False,
):
    """
    Undoes the most recent :func:`add_release`, provided its "chore" commit is
    still at HEAD: removes the release from hosting, deletes the version tag
    both locally and on the ``remote``, resets the branch to ``HEAD~`` and
    pushes it with lease. Without a ``remote``, only the local tag and commit
    are retracted. A release, which is no longer a draft, is only removed, if
    ``force`` is set.

    Resetting with ``--keep`` reverts every file committed by the release,
    which includes the changelog, the project version file and all the files
    modified by :data:`version_updaters`, so the next release bumps the
    version from the same base again.

    :param rt: runtime of the retraction
    :param git: git wrapper for the repository
    :param hosting: hosting service the release may be on
    :param remote: name of the remote to remove the tag from and push the
        reset branch to
    :param force: remove the release even if it is already published
    :returns: the retracted version tag
    :raises ReleaseError: HEAD is not a release commit with its tag, a remote
        is given on a detached HEAD, the release is already published without
        ``force`` or hosting failed to remove it
    """

    head, subject = git.head_commit()
    if not subject.startswith(RELEASE_SUBJECT_PREFIX):
        raise ReleaseError(
            f"HEAD is not a release commit: {subject!r}" if head else "No HEAD commit."
        )

    version = subject[len(RELEASE_SUBJECT_PREFIX) :].strip()
    tag = f"v{version}"
    if tag not in git.tags_at(head):
        raise ReleaseError(f"Tag {tag} does not point at HEAD ({head[:8]}).")

    branch = git.current_branch()
    if remote and not branch:
        raise ReleaseError("Cannot push retraction from a detached HEAD.")

    info = hosting.locate_release(tag)
    if info is not None and not info.is_draft and not force:
        raise ReleaseError(
            f"Release {tag} is already published; use --force-retract to retract it anyway."
        )

    if info is None:
        if hosting.is_active:
            rt.message(
                f"No release named {tag} found, skipping", level=env.Msg.STATUS
            )
    else:
        kind = "draft" if info.is_draft else "published release"
        rt.message(f"Removing {kind} {tag}", level=env.Msg.STATUS)
        if not hosting.delete_release(info):
            raise ReleaseError(f"Could not remove release {tag}.")

    if remote:
        git.delete_remote_tag(remote, tag)
    git.delete_tag(tag)
    git.reset_keep("HEAD~")
    if remote:
        git.push_with_lease(remote, branch, head)

    return tag
