"""Tests for reading changes from git in ``proj_flow.log.commit``."""

import pytest
from fakes import FakeRuntime, git_log

from proj_flow.log import commit
from proj_flow.log.commit import BREAKING_CHANGE, Git, Level, LogSetup


def H(n: int) -> str:
    """Fake full hash, unique per number."""
    return f"{n:040x}"


def setup_for(hosting=None, **kwargs) -> LogSetup:
    return LogSetup(hosting or commit.NoHosting(), None, None, omit=[], **kwargs)


def parse(*commits, setup=None, omit=frozenset()):
    git = Git(FakeRuntime())
    return git.parse_log(git_log(*commits), "--SEP--", setup or setup_for(), set(omit))


def summaries(changes):
    return {key: [link.summary for link in links] for key, links in changes.items()}


# ---------------------------------------------------------------- parse_log


def test_parse_log_groups_by_type():
    changes, level = parse(
        (H(1), "feat: first feature"),
        (H(2), "fix(io): a fix"),
        (H(3), "feat(api): second feature"),
    )
    assert summaries(changes) == {
        "feat": ["first feature", "second feature"],
        "fix": ["a fix"],
    }
    assert changes["fix"][0].scope == "io"
    assert changes["fix"][0].hash == H(2)
    assert changes["fix"][0].short_hash == H(2)[:7]
    assert level == Level.FEATURE


def test_parse_log_multiline_body_and_references():
    changes, _ = parse(
        (H(1), "fix: crash\n\nLonger description\nover lines.\n\nFixes: #12, #13"),
    )
    link = changes["fix"][0]
    assert link.summary == "crash"
    assert link.references == {"fixes": ["#12", "#13"]}


def test_parse_log_skips_non_conventional_and_empty():
    changes, level = parse(
        (H(1), "Merge branch 'x'"),
        (H(2), "fix: real one"),
    )
    assert summaries(changes) == {"fix": ["real one"]}
    assert level == Level.PATCH

    assert parse() == ({}, Level.BENIGN)


def test_parse_log_always_hides_release_and_no_log():
    changes, level = parse(
        (H(1), "chore: release 1.2.3"),
        (H(2), "feat: hidden (no-log)"),
        (H(3), "fix: visible"),
        setup=setup_for(take_all=True),
    )
    assert summaries(changes) == {"fix": ["visible"]}
    # neither the release commit nor the (no-log) one raise the level
    assert level == Level.PATCH


def test_parse_log_omits_hashes():
    changes, level = parse(
        (H(1), "feat: omitted"),
        (H(2), "fix: kept"),
        omit={H(1)},
    )
    assert summaries(changes) == {"fix": ["kept"]}
    assert level == Level.PATCH


def test_parse_log_hidden_types_still_count_for_level():
    changes, level = parse(
        (H(1), "chore: tidy up"),
        (H(2), "ci: new pipeline"),
    )
    assert changes == {}
    assert level == Level.BENIGN

    changes, level = parse((H(1), "refactor!: rename everything"))
    # hidden type, but breaking: moved to the breaking section
    assert summaries(changes) == {BREAKING_CHANGE: ["rename everything"]}
    assert level == Level.BREAKING


def test_parse_log_breaking_visible_type_stays_in_its_section():
    changes, level = parse((H(1), "feat!: new api"))
    assert summaries(changes) == {"feat": ["new api"]}
    assert changes["feat"][0].is_breaking
    assert level == Level.BREAKING


def test_parse_log_docs_become_fixes():
    changes, level = parse((H(1), "docs: explain the thing"))
    assert summaries(changes) == {"fix": ["explain the thing"]}
    assert changes["fix"][0].scope == "docs"
    assert level == Level.PATCH


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({}, {"feat": ["f"]}),
        ({"take_all": True}, {"feat": ["f"], "chore": ["c"], "ci": ["i"]}),
        ({"with_types": ["ci"]}, {"feat": ["f"], "ci": ["i"]}),
    ],
)
def test_parse_log_visibility(kwargs, expected):
    changes, _ = parse(
        (H(1), "feat: f"),
        (H(2), "chore: c"),
        (H(3), "ci: i"),
        setup=setup_for(**kwargs),
    )
    assert summaries(changes) == expected


def test_parse_log_scope_fix():
    changes, _ = parse(
        (H(1), "fix(cmkae): typo in scope"),
        setup=setup_for(scope_fix={"cmkae": "cmake"}),
    )
    assert changes["fix"][0].scope == "cmake"


# ------------------------------------------------------------- commit_range


@pytest.mark.parametrize(
    "prev_tag, curr_tag, expected",
    [
        (None, None, None),
        (None, "v1.0.0", "v1.0.0"),
        ("v1.0.0", None, "v1.0.0..HEAD"),
        ("v1.0.0", "v1.1.0", "v1.0.0..v1.1.0"),
    ],
)
def test_commit_range(prev_tag, curr_tag, expected):
    setup = LogSetup(commit.NoHosting(), prev_tag, curr_tag, omit=[])
    assert setup.commit_range == expected


# ------------------------------------------------------------------ get_log


@pytest.fixture
def separator():
    old = commit.COMMIT_SEP
    commit.set_commit_sep("--SEP--")
    yield "--SEP--"
    commit.set_commit_sep(old)


def test_get_log_runs_git_with_range_and_omits(separator):
    log_format = f"--format=%h %H%n%B%n{separator}"
    rt = FakeRuntime()
    rt.respond("git", "log", "--format=%H", "v0.9.0", stdout=f"{H(1)}\n{H(2)}\n")
    rt.respond(
        "git",
        "log",
        log_format,
        stdout=git_log(
            (H(1), "feat: in omitted range"),
            (H(3), "fix: kept"),
        ),
    )

    setup = LogSetup(commit.NoHosting(), "v1.0.0", None, omit=["v0.9.0"])
    changes, level = Git(rt).get_log(setup, silent=True)

    assert summaries(changes) == {"fix": ["kept"]}
    assert level == Level.PATCH
    assert rt.captured == [
        ("git", "log", "--format=%H", "v0.9.0"),
        ("git", "log", log_format, "v1.0.0..HEAD"),
    ]


def test_get_log_without_range(separator):
    rt = FakeRuntime()
    Git(rt).get_log(setup_for(), silent=True)
    assert rt.captured == [("git", "log", f"--format=%h %H%n%B%n{separator}")]


# -------------------------------------------------------------- git helpers


def test_tag_list_orders_versions():
    rt = FakeRuntime().respond(
        "git",
        "tag",
        stdout="v1.10.0\nv1.2.0\nnot-a-version\nv1.2.0-rc.1\nvbroken\nv0.9\n",
    )
    assert Git(rt).tag_list() == ["v0.9", "v1.2.0-rc.1", "v1.2.0", "v1.10.0"]


def test_remotes():
    rt = FakeRuntime().respond(
        "git",
        "remote",
        "-v",
        stdout=(
            "origin\thttps://github.com/o/r.git (fetch)\n"
            "origin\thttps://github.com/o/r.git (push)\n"
            "weird\tno-usage-suffix\n"
            "\n"
        ),
    )
    remotes = list(Git(rt).remotes())
    assert remotes == [
        commit.Remote("origin", "fetch", "https://github.com/o/r.git"),
        commit.Remote("origin", "push", "https://github.com/o/r.git"),
    ]


def test_head_commit_and_tags_at():
    rt = FakeRuntime()
    rt.respond("git", "log", "-1", stdout=f"{H(7)}\nchore: release 1.0.0\n")
    rt.respond("git", "tag", "--points-at", stdout="v1.0.0\nlatest\n")
    rt.respond("git", "branch", "--show-current", stdout="main\n")
    git = Git(rt)

    assert git.head_commit() == (H(7), "chore: release 1.0.0")
    assert git.tags_at(H(7)) == ["v1.0.0", "latest"]
    assert git.current_branch() == "main"


def test_head_commit_failure():
    rt = FakeRuntime().respond("git", "log", "-1", returncode=128)
    assert Git(rt).head_commit() == ("", "")


def test_mutating_commands():
    rt = FakeRuntime()
    git = Git(rt)
    git.add_files("a", "b")
    git.commit("msg")
    git.annotated_tag("v1.0.0", "release 1.0.0")
    git.push_with_refs("origin", "main")
    git.delete_tag("v1.0.0")
    git.delete_remote_tag("origin", "v1.0.0")
    git.reset_keep("HEAD~")
    git.push_with_lease("origin", "main", H(1))

    assert rt.calls == [
        ("git", "add", "a", "b"),
        ("git", "commit", "-m", "msg"),
        ("git", "tag", "-am", "release 1.0.0", "v1.0.0"),
        ("git", "push", "origin", "main", "--follow-tags", "--force-with-lease"),
        ("git", "tag", "-d", "v1.0.0"),
        ("git", "push", "origin", "--delete", "refs/tags/v1.0.0"),
        ("git", "reset", "--keep", "HEAD~"),
        (
            "git",
            "push",
            "origin",
            "HEAD:refs/heads/main",
            f"--force-with-lease=refs/heads/main:{H(1)}",
        ),
    ]


def test_read_tag_date():
    rt = FakeRuntime().respond(
        "git", "log", "-n1", stdout="2026-11-15T10:00:00+01:00\n"
    )
    assert commit.read_tag_date("v1.0.0", rt) == "2026-11-15"


def test_read_tag_date_falls_back_to_today(monkeypatch):
    monkeypatch.setattr(commit.time, "strftime", lambda fmt: "2000-01-02")
    rt = FakeRuntime().respond("git", "log", "-n1", returncode=128)
    assert commit.read_tag_date("missing", rt) == "2000-01-02"
