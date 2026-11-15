"""Tests for making and retracting releases in ``proj_flow.log.release``."""

import textwrap

import pytest
from fakes import FakeHosting, FakeRuntime, git_log

from proj_flow.api import release as api_release
from proj_flow.ext.python.version import ProjectSuite
from proj_flow.log import commit, release
from proj_flow.log.commit import Level
from proj_flow.log.error import NoProjectError, ReleaseError, VersionNotAdvancing
from proj_flow.log.rich_text import markdown

HEAD = "f" * 40
VERSION_FILE = "src/my_package/__init__.py"

# ------------------------------------------------------------ _bump_version


@pytest.mark.parametrize(
    "version, level, expected",
    [
        ("1.2.3", Level.BENIGN, "1.2.3"),
        ("1.2.3", Level.PATCH, "1.2.4"),
        ("1.2.3", Level.FEATURE, "1.3.0"),
        ("1.2.3", Level.BREAKING, "2.0.0"),
        ("0.9", Level.PATCH, "0.9.1"),
        ("1", Level.FEATURE, "1.1.0"),
        ("1.2.3.4", Level.PATCH, "1.2.4"),
        # benign changes keep the version, suffix included
        ("1.2.3-rc.1", Level.BENIGN, "1.2.3-rc.1"),
        # pre-release of a major: anything up to breaking just releases it
        ("2.0.0-rc.1", Level.PATCH, "2.0.0"),
        ("2.0.0-rc.1", Level.FEATURE, "2.0.0"),
        ("2.0.0-rc.1", Level.BREAKING, "2.0.0"),
        # pre-release of a minor: breaking needs a new major
        ("1.3.0-beta", Level.PATCH, "1.3.0"),
        ("1.3.0-beta", Level.FEATURE, "1.3.0"),
        ("1.3.0-beta", Level.BREAKING, "2.0.0"),
        # pre-release of a patch: features and breaking go higher
        ("1.2.4-alpha.2", Level.PATCH, "1.2.4"),
        ("1.2.4-alpha.2", Level.FEATURE, "1.3.0"),
        ("1.2.4-alpha.2", Level.BREAKING, "2.0.0"),
        # PEP 440 pre-releases
        ("1.3.0rc1", Level.PATCH, "1.3.0"),
        ("1.3.0.dev0", Level.FEATURE, "1.3.0"),
        ("1.2.4b2", Level.FEATURE, "1.3.0"),
        # post-releases follow their release
        ("1.2.3.post1", Level.PATCH, "1.2.4"),
        ("1.2.3-post.1", Level.FEATURE, "1.3.0"),
        # build metadata is dropped
        ("1.2.3+build.7", Level.PATCH, "1.2.4"),
        ("2.0.0-rc.1+build.7", Level.PATCH, "2.0.0"),
    ],
)
def test_bump_version(version, level, expected):
    assert release._bump_version(version, level) == expected


def test_bump_version_rejects_garbage():
    with pytest.raises(ValueError, match="not a version"):
        release._bump_version("latest", Level.PATCH)


# -------------------------------------------------------------- add_release


@pytest.fixture
def separator():
    old = commit.COMMIT_SEP
    commit.set_commit_sep("--SEP--")
    yield "--SEP--"
    commit.set_commit_sep(old)


@pytest.fixture
def project(tmp_path, tmp_path_factory, monkeypatch):
    """
    A Python project at 1.2.3, the only project suite and no updaters. The
    tests run outside of the project, to see all files are found through
    the runtime's root.
    """
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""
            [project]
            name = "my-package"
            dynamic = ["version"]

            [tool.hatch.version]
            path = "src/my_package/__init__.py"

            [tool.hatch.build.targets.wheel]
            packages = ["src/my_package"]
            """),
        encoding="UTF-8",
    )
    version_file = tmp_path / VERSION_FILE
    version_file.parent.mkdir(parents=True)
    version_file.write_text('__version__ = "1.2.3"\n', encoding="UTF-8")

    monkeypatch.setattr(api_release.project_suites, "container", [ProjectSuite()])
    monkeypatch.setattr(release.version_updaters, "container", [])
    monkeypatch.chdir(tmp_path_factory.mktemp("elsewhere"))
    return tmp_path


def release_rt(root, separator, *messages, tags="v1.2.3\n", dry_run=False):
    rt = FakeRuntime(root=root, dry_run=dry_run)
    rt.respond("git", "tag", stdout=tags)
    rt.respond("git", "log", "-n1", stdout="2026-11-15T10:00:00+01:00\n")
    rt.respond(
        "git",
        "log",
        f"--format=%h %H%n%B%n{separator}",
        stdout=git_log(*((f"{n:040x}", m) for n, m in enumerate(messages, 1))),
    )
    return rt


def run_add_release(rt, hosting=None, forced_level=None, draft=True):
    return release.add_release(
        rt,
        dbg_changelog=False,
        forced_level=forced_level,
        take_all=False,
        with_types=[],
        draft=draft,
        generator=markdown.ChangelogGenerator(),
        omit=[],
        git=commit.Git(rt),
        hosting=hosting or FakeHosting(),
    )


def test_add_release(project, separator):
    rt = release_rt(project, separator, "feat(api): new call", "fix: crash")
    hosting = FakeHosting()

    tag = run_add_release(rt, hosting)

    assert tag == "v1.3.0"
    assert (project / VERSION_FILE).read_text(encoding="UTF-8") == (
        '__version__ = "1.3.0"\n'
    )
    changelog = (project / "CHANGELOG.md").read_text(encoding="UTF-8")
    assert "1.3.0" in changelog and "new call" in changelog

    assert ("git", "log", f"--format=%h %H%n%B%n{separator}", "v1.2.3..HEAD") in (
        rt.captured
    )
    add, git_commit, git_tag = rt.calls
    assert add == ("git", "add", "CHANGELOG.md", VERSION_FILE)
    assert git_commit[:3] == ("git", "commit", "-m")
    assert git_commit[3].startswith("chore: release 1.3.0\n\nNew Features:\n\n")
    assert " - api: new call (" in git_commit[3]
    assert git_tag == ("git", "tag", "-am", "release 1.3.0", "v1.3.0")

    log, curr_tag, draft = hosting.added[0]
    assert (curr_tag, draft) == ("v1.3.0", True)
    assert set(log) == {"feat", "fix"}
    assert any(m.startswith("Visit draft at") for m in rt.messages)


def test_add_release_dry_run_leaves_files(project, separator):
    rt = release_rt(project, separator, "fix: crash", dry_run=True)

    assert run_add_release(rt) == "v1.2.4"

    assert (project / VERSION_FILE).read_text(encoding="UTF-8") == (
        '__version__ = "1.2.3"\n'
    )
    assert not (project / "CHANGELOG.md").exists()
    # files are still listed, so the printed commands are complete
    assert rt.calls[0] == ("git", "add", "CHANGELOG.md", VERSION_FILE)


def test_add_release_forced_level(project, separator):
    rt = release_rt(project, separator, "fix: crash")
    assert run_add_release(rt, forced_level=Level.BREAKING) == "v2.0.0"


def test_add_release_first_release(project, separator):
    rt = release_rt(project, separator, "feat: everything", tags="")
    assert run_add_release(rt) == "v1.3.0"
    # no previous tag: the whole history is read
    assert ("git", "log", f"--format=%h %H%n%B%n{separator}") in rt.captured


def test_add_release_nothing_to_release(project, separator):
    rt = release_rt(project, separator, "chore: tidy", "ci: pipeline")
    with pytest.raises(VersionNotAdvancing) as error:
        run_add_release(rt)
    assert error.value.version == "1.2.3"
    assert rt.calls == []


def test_add_release_existing_tag(project, separator):
    rt = release_rt(project, separator, "feat: x", tags="v1.2.3\nv1.3.0\n")
    with pytest.raises(SystemExit, match="Tag v1.3.0 already exists"):
        run_add_release(rt)
    assert rt.calls == []


def test_add_release_no_project(tmp_path, monkeypatch, separator):
    monkeypatch.setattr(api_release.project_suites, "container", [ProjectSuite()])
    rt = release_rt(tmp_path, separator, "feat: x")
    with pytest.raises(NoProjectError):
        run_add_release(rt)


def test_add_release_inactive_hosting(project, separator):
    rt = release_rt(project, separator, "fix: crash")
    hosting = FakeHosting(active=False)
    run_add_release(rt, hosting)
    assert hosting.added == []
    assert not any(m.startswith("Visit") for m in rt.messages)


def test_add_release_published_message(project, separator):
    rt = release_rt(project, separator, "fix: crash")
    run_add_release(rt, draft=False)
    assert any(m.startswith("Visit release at") for m in rt.messages)


def test_add_release_version_updaters(project, separator, monkeypatch):
    seen = []

    class One(release.VersionUpdater):
        def on_version_change(self, rt, new_version):
            seen.append(new_version)
            return "one.txt"

    class Many(release.VersionUpdater):
        def on_version_change_tags(self, rt, new_version, tags):
            seen.append(tags)
            return ["two.txt", "three.txt"]

    class Nothing(release.VersionUpdater):
        pass

    monkeypatch.setattr(
        release.version_updaters, "container", [One(), Many(), Nothing()]
    )
    rt = release_rt(project, separator, "fix: crash")
    run_add_release(rt)

    assert seen == ["1.2.4", ["v1.2.3"]]
    assert rt.calls[0] == (
        "git",
        "add",
        "CHANGELOG.md",
        VERSION_FILE,
        "one.txt",
        "two.txt",
        "three.txt",
    )


def test_add_release_from_prerelease(project, separator):
    version_file = project / VERSION_FILE
    version_file.write_text('__version__ = "2.0.0-rc.1"\n', encoding="UTF-8")
    rt = release_rt(project, separator, "fix: last fix", tags="v2.0.0-rc.1\n")

    assert run_add_release(rt) == "v2.0.0"
    assert version_file.read_text(encoding="UTF-8") == '__version__ = "2.0.0"\n'


def test_add_release_prerelease_without_changes(project, separator):
    (project / VERSION_FILE).write_text(
        '__version__ = "2.0.0-rc.1"\n', encoding="UTF-8"
    )
    rt = release_rt(project, separator, "chore: tidy", tags="v2.0.0-rc.1\n")

    with pytest.raises(VersionNotAdvancing) as error:
        run_add_release(rt)
    assert error.value.version == "2.0.0-rc.1"


def test_set_version_outside_project_dir(project):
    # the project fixture runs the test from another directory
    ProjectSuite().set_version(FakeRuntime(root=project), "1.3.0")
    assert (project / VERSION_FILE).read_text(encoding="UTF-8") == (
        '__version__ = "1.3.0"\n'
    )


# ---------------------------------------------------------- retract_release


def retract_rt(subject="chore: release 1.3.0", tags="v1.3.0\n", branch="main"):
    rt = FakeRuntime()
    rt.respond("git", "log", "-1", stdout=f"{HEAD}\n{subject}\n")
    rt.respond("git", "tag", "--points-at", stdout=tags)
    rt.respond("git", "branch", "--show-current", stdout=f"{branch}\n")
    return rt


def run_retract(rt, hosting, remote="origin", force=False):
    return release.retract_release(rt, commit.Git(rt), hosting, remote, force)


def test_retract_draft_with_remote():
    rt = retract_rt()
    draft = commit.ReleaseInfo(is_draft=True, tag="v1.3.0")
    hosting = FakeHosting(release=draft)

    assert run_retract(rt, hosting) == "v1.3.0"

    assert hosting.deleted == [draft]
    assert rt.calls == [
        ("git", "push", "origin", "--delete", "refs/tags/v1.3.0"),
        ("git", "tag", "-d", "v1.3.0"),
        ("git", "reset", "--keep", "HEAD~"),
        (
            "git",
            "push",
            "origin",
            "HEAD:refs/heads/main",
            f"--force-with-lease=refs/heads/main:{HEAD}",
        ),
    ]


def test_retract_local_only():
    rt = retract_rt(branch="")
    hosting = FakeHosting(release=None)

    assert run_retract(rt, hosting, remote=None) == "v1.3.0"

    assert rt.calls == [
        ("git", "tag", "-d", "v1.3.0"),
        ("git", "reset", "--keep", "HEAD~"),
    ]
    assert any("No release named v1.3.0" in m for m in rt.messages)


def test_retract_published_needs_force():
    published = commit.ReleaseInfo(is_draft=False, tag="v1.3.0")

    rt = retract_rt()
    with pytest.raises(ReleaseError) as error:
        run_retract(rt, FakeHosting(release=published))
    assert "already published" in str(error.value)
    assert rt.calls == []

    hosting = FakeHosting(release=published)
    assert run_retract(retract_rt(), hosting, force=True) == "v1.3.0"
    assert hosting.deleted == [published]


@pytest.mark.parametrize(
    "rt_kwargs, kwargs, message",
    [
        ({"subject": "feat: not a release"}, {}, "HEAD is not a release commit"),
        ({"tags": "v1.2.0\n"}, {}, "Tag v1.3.0 does not point at HEAD"),
        ({"branch": ""}, {}, "detached HEAD"),
        ({}, {"delete_ok": False}, "Could not remove release v1.3.0"),
    ],
)
def test_retract_errors(rt_kwargs, kwargs, message):
    rt = retract_rt(**rt_kwargs)
    hosting = FakeHosting(release=commit.ReleaseInfo(is_draft=True), **kwargs)
    with pytest.raises(ReleaseError) as error:
        run_retract(rt, hosting)
    assert message in str(error.value)
    assert rt.calls == []


def test_retract_without_head():
    rt = FakeRuntime().respond("git", "log", "-1", returncode=128)
    with pytest.raises(ReleaseError) as error:
        run_retract(rt, FakeHosting())
    assert str(error.value) == "No HEAD commit."


# ------------------------------------------------------------------- errors


def test_error_messages_are_in_str():
    assert str(ReleaseError("went wrong")) == "went wrong"
    assert str(NoProjectError()) == "No project definition found."

    error = VersionNotAdvancing("1.2.3")
    assert str(error) == "[1.2.3] Version did not change, not doing anything."
    assert error.version == "1.2.3"

    for error in [ReleaseError("x"), NoProjectError(), VersionNotAdvancing("1")]:
        assert not hasattr(error, "message")
