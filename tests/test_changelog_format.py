"""Tests for changelog formatting in ``proj_flow.log.msg`` and ``rich_text``."""

import pytest
from fakes import FakeHosting, FakeRuntime, git_log, make_link

from proj_flow.log import commit, fmt, msg
from proj_flow.log.commit import BREAKING_CHANGE, LogSetup
from proj_flow.log.rich_text import markdown, re_structured_text

H1, H2, H3, H4, H5 = (f"{n}" * 40 for n in range(1, 6))
URL = "https://host.test/owner/repo"


@pytest.fixture
def log() -> commit.ChangeLog:
    return {
        "feat": [
            make_link("new thing", scope="api", hash=H1),
            make_link("other thing", hash=H2),
        ],
        "fix": [
            make_link(
                "a `bug`",
                scope="io",
                hash=H3,
                references={"fixes": ["#1", "#2", "JIRA-3"], "references": [""]},
            )
        ],
        BREAKING_CHANGE: [
            make_link(
                "old api removed",
                scope="core",
                hash=H4,
                breaking=True,
                breaking_message=["Use the   new\n api.", "  "],
            )
        ],
        "perf": [make_link("faster", hash=H5)],
    }


def release_setup(hosting=None, prev="v1.0.0", curr="v1.1.0"):
    return LogSetup(hosting or commit.NoHosting(), prev, curr, omit=[])


# --------------------------------------------------------- ChangelogMessage


def test_default_markdown_message(log):
    text = msg.ChangelogMessage().format_changelog(log)
    assert text == "\n".join(
        [
            "### Breaking",
            "",
            "- core: old api removed (4444444)",
            "",
            "### New Features",
            "",
            # empty scope sorts first
            "- other thing (2222222)",
            "- api: new thing (1111111)",
            "",
            "### Bug Fixes",
            "",
            "- io: a `bug` (3333333), fixes #1, #2 and JIRA-3",
            "",
            "### Performance Improvements",
            "",
            "- faster (5555555)",
            "",
            "### BREAKING CHANGES",
            "",
            "Use the new api.\n",
        ]
    )


def test_breaking_marker_in_visible_sections():
    log = {
        "feat": [make_link("x", scope="api", breaking=True)],
        "fix": [make_link("y", breaking=True)],
        "custom": [make_link("z")],
    }
    text = msg.ChangelogMessage().format_changelog(log)
    assert "- breaking, api: x (aaaaaaa)" in text
    assert "- breaking: y (aaaaaaa)" in text
    # unknown type uses its own name as the header
    assert "### custom" in text


def test_nothing_to_report():
    assert msg.ChangelogMessage().format_changelog({}) == "*Nothing to report.*\n"


def test_single_reference():
    link = make_link("x", references={"closes": ["#9"]})
    assert msg.ChangelogMessage().link_str(link, False) == "- x (aaaaaaa), closes #9"


# ------------------------------------------------------------ CommitMessage


def test_commit_message(log):
    text = fmt.format_commit_message(log)
    assert text == "\n".join(
        [
            "",
            "",
            "Breaking:",
            "",
            " - core: old api removed (4444444)",
            "",
            "New Features:",
            "",
            " - other thing (2222222)",
            " - api: new thing (1111111)",
            "",
            "Bug Fixes:",
            "",
            " - io: a `bug` (3333333), fixes #1, #2 and JIRA-3",
            "",
            "Performance Improvements:",
            "",
            " - faster (5555555)",
            "",
            "BREAKING CHANGES:",
            "",
            "Use the new api.",
        ]
    )
    assert msg.format_commit_message(log) == text


def test_commit_message_nothing_to_report():
    assert fmt.format_commit_message({}) == "\n\n*Nothing to report.*"


def test_wrap_at_78_paragraph():
    para = " ".join(["word"] * 40)
    wrapped = msg.CommitMessage.wrap_at_78(para)
    lines = wrapped.split("\n")
    assert all(len(line) <= 78 for line in lines)
    assert len(lines) > 1
    assert " ".join(lines) == para


def test_wrap_at_78_list_items():
    item = " - " + " ".join(["lorem"] * 20)
    wrapped = msg.CommitMessage.wrap_at_78(f"{item}\n - short")
    lines = wrapped.split("\n")
    assert lines[0].startswith(" - lorem")
    assert lines[1].startswith("   lorem")
    assert lines[-1] == " - short"
    assert all(len(line) <= 75 for line in lines)


def test_wrap_at_78_collapses_spaces():
    assert msg.CommitMessage.wrap_at_78("a   b  c") == "a b c"
    assert msg.CommitMessage.wrap_at_78("") == ""


# ----------------------------------------------------------- ReleaseMessage


def test_release_message_with_links(log):
    hosting = FakeHosting()
    text = msg.ReleaseMessage(release_setup(hosting)).format_changelog(log)

    assert f"- **api**: new thing ([1111111]({URL}/commit/{H1}))" in text
    assert f"- other thing ([2222222]({URL}/commit/{H2}))" in text
    assert text.endswith(f"**Full Changelog**: {URL}/compare/v1.0.0...v1.1.0")


def test_release_message_without_hosting(log):
    text = msg.ReleaseMessage(release_setup()).format_changelog(log)
    assert "- **api**: new thing (1111111)" in text
    assert "Full Changelog" not in text


# ------------------------------------------------------- Markdown file part


def test_markdown_file_update(log):
    hosting = FakeHosting()
    text = markdown.FileUpdate(release_setup(hosting), "2026-11-15").format_changelog(
        log
    )
    lines = text.split("\n")
    assert lines[0] == f"## [1.1.0]({URL}/compare/v1.0.0...v1.1.0) (2026-11-15)"
    assert (
        f"- **io**: a `bug` ([3333333]({URL}/commit/{H3})), fixes "
        f"[#1]({URL}/issues/1), [#2]({URL}/issues/2) and JIRA-3"
    ) in lines
    assert "Full Changelog" not in text


def test_markdown_file_update_without_hosting():
    text = markdown.FileUpdate(release_setup(), "2026-11-15").format_changelog({})
    assert text == "## 1.1.0 (2026-11-15)\n\n*Nothing to report.*\n"

    unknown = release_setup(curr=None)
    text = markdown.FileUpdate(unknown, "2026-11-15").format_changelog({})
    assert text.startswith("## *unknown* (2026-11-15)")


# ------------------------------------------------ reStructuredText file part


def test_rst_file_update(log):
    hosting = FakeHosting()
    text = re_structured_text.FileUpdate(
        release_setup(hosting), "2026-11-15"
    ).format_changelog(log)
    lines = text.split("\n")

    heading = f"`1.1.0 <{URL}/compare/v1.0.0...v1.1.0>`_ (2026-11-15)"
    assert lines[:3] == [heading, "=" * len(heading), ""]
    assert "New Features\n------------\n" in text
    # backticks are escaped
    assert f"- **io**: a ``bug`` (`3333333 <{URL}/commit/{H3}>`_)" in text


def test_rst_file_update_without_hosting():
    text = re_structured_text.FileUpdate(
        release_setup(), "2026-11-15"
    ).format_changelog({"fix": [make_link("x")]})
    assert text.split("\n")[:6] == [
        "1.1.0 (2026-11-15)",
        "==================",
        "",
        "Bug Fixes",
        "---------",
        "",
    ]
    assert "- x (aaaaaaa)" in text


# ---------------------------------------------------------------- generators


@pytest.fixture
def dated_rt(tmp_path):
    return FakeRuntime(root=tmp_path).respond(
        "git", "log", "-n1", stdout="2026-11-15T10:00:00+01:00\n"
    )


@pytest.mark.parametrize(
    "generator, filename",
    [
        (markdown.ChangelogGenerator(), "CHANGELOG.md"),
        (re_structured_text.ChangelogGenerator(), "CHANGELOG.rst"),
    ],
)
def test_update_changelog_creates_file(dated_rt, generator, filename):
    log = {"feat": [make_link("first")]}
    generator.update_changelog(log, release_setup(None, None, "v0.1.0"), dated_rt)

    text = (dated_rt.root / filename).read_text(encoding="UTF-8")
    assert generator.filename == filename
    assert text.startswith(generator.intro())
    assert "0.1.0 (2026-11-15)" in text
    assert "first (aaaaaaa)" in text


@pytest.mark.parametrize(
    "generator",
    [markdown.ChangelogGenerator(), re_structured_text.ChangelogGenerator()],
)
@pytest.mark.parametrize("hosting", [None, FakeHosting()])
def test_update_changelog_inserts_newest_first(dated_rt, generator, hosting):
    path = dated_rt.root / generator.filename
    versions = [("v0.1.0", None), ("v0.2.0", "v0.1.0"), ("v1.0.0", "v0.2.0")]
    for curr, prev in versions:
        generator.update_changelog(
            {"fix": [make_link(f"fix for {curr}")]},
            release_setup(hosting, prev, curr),
            dated_rt,
        )

    text = path.read_text(encoding="UTF-8")
    assert text.startswith(generator.intro())
    positions = [text.index(f"fix for {curr}") for curr, _ in versions]
    assert positions == sorted(positions, reverse=True)
    # exactly one intro
    assert text.count(generator.intro_head) == 1


def test_rst_split_matches_this_repository():
    import re
    from pathlib import Path

    generator = re_structured_text.ChangelogGenerator()
    changelog = Path(__file__).resolve().parent.parent / "CHANGELOG.rst"
    text = changelog.read_text(encoding="UTF-8")

    assert re.search(generator.split_re, text, flags=re.MULTILINE)


def test_rst_intro_is_wrapped():
    generator = re_structured_text.ChangelogGenerator()
    assert generator.intro() == "\n".join(
        [
            "=========",
            "Changelog",
            "=========",
            "",
            "All notable changes to this project will be documented in this file.",
            "",
        ]
    )


@pytest.fixture
def separator():
    old = commit.COMMIT_SEP
    commit.set_commit_sep("--SEP--")
    yield "--SEP--"
    commit.set_commit_sep(old)


def test_create_changelog(dated_rt, separator):
    log_format = f"--format=%h %H%n%B%n{separator}"
    dated_rt.respond(
        "git", "log", log_format, "v0.1.0", stdout=git_log((H1, "feat: initial"))
    )
    dated_rt.respond(
        "git",
        "log",
        log_format,
        "v0.1.0..v0.2.0",
        stdout=git_log((H2, "fix: second"), (H3, "chore: hidden")),
    )
    generator = markdown.ChangelogGenerator()

    generator.create_changelog(
        ["v0.1.0", "v0.2.0"], commit.Git(dated_rt), commit.NoHosting(), dated_rt
    )

    text = (dated_rt.root / "CHANGELOG.md").read_text(encoding="UTF-8")
    assert text.startswith(generator.intro())
    assert text.index("## 0.2.0") < text.index("## 0.1.0")
    assert "- second (2222222)" in text
    assert "- initial (1111111)" in text
    assert "hidden" not in text
