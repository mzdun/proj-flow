"""Tests for Conventional Commit parsing in ``proj_flow.log.commit``."""

import pytest

from proj_flow.log import commit
from proj_flow.log.commit import Level


def parse(message: str):
    return commit._get_commit("0123456789abcdef", "0123456", message)


def test_simple_feature():
    result = parse("feat: add a thing")
    assert result is not None
    assert result.type == "feat"
    assert result.link.scope == ""
    assert result.link.summary == "add a thing"
    assert result.link.hash == "0123456789abcdef"
    assert result.link.short_hash == "0123456"
    assert not result.link.is_breaking
    assert result.link.breaking_message == []
    assert result.link.references == {}


def test_scope():
    result = parse("fix(cmake): handle (nested) parens")
    assert result is not None
    assert result.type == "fix"
    assert result.link.scope == "cmake"
    assert result.link.summary == "handle (nested) parens"


@pytest.mark.parametrize(
    "message",
    ["just a message", "", ": no type", "feat:missing space"],
)
def test_not_a_conventional_commit(message):
    assert parse(message) is None


def test_breaking_by_bang():
    result = parse("feat(api)!: drop old call")
    assert result is not None
    assert result.type == "feat"
    assert result.link.scope == "api"
    assert result.link.is_breaking
    assert result.link.breaking_message == []


def test_breaking_by_footer_paragraph():
    result = parse(
        "refactor: rename things\n\n"
        "Some description.\n\n"
        "BREAKING CHANGE: the old name\nis gone.\n\n"
        "Use the new one."
    )
    assert result is not None
    assert result.link.is_breaking
    assert result.link.breaking_message == ["the old name is gone.", "Use the new one."]


def test_references():
    result = parse(
        "fix: crash on start\n\n"
        "Body text.\n\n"
        "Refs: #1, #2\n"
        "Closes: #3\n"
        "Reviewed-by: someone"
    )
    assert result is not None
    assert result.link.references == {"references": ["#1", "#2"], "closes": ["#3"]}


@pytest.mark.parametrize(
    "message, level, scope",
    [
        ("feat(x): y", Level.FEATURE, "x"),
        ("fix(x): y", Level.PATCH, "x"),
        ("docs: y", Level.PATCH, "docs"),
        ("chore(x): y", Level.BENIGN, "x"),
        ("chore(x)!: y", Level.BREAKING, "x"),
    ],
)
def test_level_from_commit(message, level, scope):
    result = parse(message)
    assert result is not None
    assert commit._level_from_commit(result) == (level, scope)


@pytest.mark.parametrize(
    "tag, expected",
    [
        ("1.2.3", [1, 2, 3, ""]),
        ("1.2", [1, 2, 0, ""]),
        ("2", [2, 0, 0, ""]),
        ("1.0.0-rc.1", [1, 0, 0, "rc.1"]),
    ],
)
def test_sem_ver(tag, expected):
    assert commit._sem_ver(tag) == expected


def test_sem_ver_ordering():
    tags = ["1.10.0", "1.2.0", "1.2.10", "1.2.9"]
    assert sorted(tags, key=commit._sem_ver) == ["1.2.0", "1.2.9", "1.2.10", "1.10.0"]


def test_forced_levels_cover_all_bumps():
    assert set(commit.FORCED_LEVEL.values()) == {
        Level.PATCH,
        Level.FEATURE,
        Level.BREAKING,
    }
