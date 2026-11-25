"""Tests for the checks of ``proj-flow github release``."""

import pytest
from fakes import FakeRuntime

from proj_flow.ext.github import cli
from proj_flow.log import commit


@pytest.fixture(autouse=True)
def no_github_actions(monkeypatch):
    for name in ["GITHUB_ACTIONS", "GITHUB_BASE_REF", "GITHUB_REF_NAME"]:
        monkeypatch.delenv(name, raising=False)


def branch_rt(branch: str, dry_run: bool = False):
    rt = FakeRuntime(dry_run=dry_run)
    rt._cfg["default-branch"] = "main"
    rt.respond("git", "branch", "--show-current", stdout=f"{branch}\n")
    return rt


def check(rt):
    cli._check_default_branch(rt, commit.Git(rt))


def test_default_branch_passes():
    rt = branch_rt("main")
    check(rt)
    assert rt.messages == []


@pytest.mark.parametrize(
    "branch, current", [("feature", "`feature`"), ("", "a detached HEAD")]
)
def test_other_branch_fails(branch, current):
    with pytest.raises(SystemExit) as error:
        check(branch_rt(branch))
    assert str(error.value) == (
        f"Releases are made from `main`, currently on {current}."
    )


@pytest.mark.parametrize("branch", ["feature", ""])
def test_other_branch_warns_with_dry_run(branch):
    rt = branch_rt(branch, dry_run=True)
    check(rt)
    assert len(rt.messages) == 1
    assert rt.messages[0].startswith("Releases are made from `main`")
    assert rt.messages[0].endswith("Continuing with --dry-run.")


@pytest.mark.parametrize(
    "env, passes",
    [
        ({"GITHUB_BASE_REF": "main", "GITHUB_REF_NAME": "1/merge"}, True),
        ({"GITHUB_BASE_REF": "", "GITHUB_REF_NAME": "main"}, True),
        ({"GITHUB_REF_NAME": "feature"}, False),
    ],
)
def test_detached_head_in_github_actions(monkeypatch, env, passes):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    rt = branch_rt("")
    if passes:
        check(rt)
    else:
        with pytest.raises(SystemExit):
            check(rt)
