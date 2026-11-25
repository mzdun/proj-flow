"""Fakes for tests of code running git and gh through the runtime."""

import subprocess
from pathlib import Path
from typing import Optional

from proj_flow.api.env import Runtime
from proj_flow.log import commit


class FakeRuntime(Runtime):
    """
    Stands in for :class:`proj_flow.api.env.Runtime`. Records every command
    and answers :meth:`capture` with canned output, matched by the longest
    command prefix in ``responses``. Unmatched commands succeed with no
    output. :meth:`Runtime.__init__` is not called, as it would load the
    configuration; the fields it sets are set here instead.
    """

    def __init__(
        self,
        root: Optional[Path] = None,
        responses: Optional[dict] = None,
        dry_run: bool = False,
    ):
        self.root = root or Path()
        self.responses: dict[tuple[str, ...], tuple[int, str]] = responses or {}
        self.dry_run = dry_run
        # the rest of what Runtime(rt, rt) copies
        self.silent = False
        self.verbose = False
        self.official = False
        self.no_coverage = False
        self.use_color = False
        self.only_host = False
        self.platform = "linux"
        self.secrets: list[str] = []
        self._cfg: dict = {}
        self.steps: list = []
        self.aliases: list = []
        self.calls: list[tuple[str, ...]] = []
        self.captured: list[tuple[str, ...]] = []
        self.messages: list[str] = []

    def respond(self, *prefix: str, stdout: str = "", returncode: int = 0):
        self.responses[prefix] = (returncode, stdout)
        return self

    def capture(self, *args: str, silent=False):
        self.captured.append(args)
        match = max(
            (p for p in self.responses if args[: len(p)] == p),
            key=len,
            default=None,
        )
        code, out = self.responses[match] if match is not None else (0, "")
        return subprocess.CompletedProcess(args, code, out, "")

    def cmd(self, *args: str):
        self.calls.append(args)

    def print(self, *args: str, raw=False):
        pass

    def message(self, *args: str, **kwargs):
        self.messages.append(" ".join(str(arg) for arg in args))

    def fatal(self, *args: str, **kwargs):
        raise SystemExit(" ".join(args))


class FakeHosting(commit.Hosting):
    """
    Hosting generating ``https://host.test`` links and recording releases.
    Issue references in ``#<number>`` form get a link, others do not.
    """

    def __init__(self, active: bool = True, release=None, delete_ok: bool = True):
        super().__init__("https://host.test/owner/repo")
        self.active = active
        self.release = release
        self.delete_ok = delete_ok
        self.added: list[tuple] = []
        self.deleted: list[commit.ReleaseInfo] = []

    @property
    def is_active(self) -> bool:
        return self.active

    def single_commit_link(self, link: commit.Link):
        return f"{self.host_link}/commit/{link.hash}"

    def commit_listing_link(self, setup: commit.LogSetup):
        return f"{self.host_link}/compare/{setup.prev_tag}...{setup.curr_tag}"

    def reference_link(self, ref: str):
        if ref.startswith("#"):
            return f"{self.host_link}/issues/{ref[1:]}"
        return None

    def add_release(self, log, setup, git, draft):
        self.added.append((log, setup.curr_tag, draft))
        return commit.ReleaseInfo(
            url=f"{self.host_link}/releases/{setup.curr_tag}",
            is_draft=draft,
            tag=setup.curr_tag,
        )

    def locate_release(self, release_name: str):
        return self.release

    def upload_to_release(self, release, directory, names):
        return None

    def publish(self, release):
        return release

    def delete_release(self, release):
        self.deleted.append(release)
        return self.delete_ok


def make_link(
    summary: str = "do things",
    scope: str = "",
    hash: str = "a" * 40,
    breaking: bool = False,
    breaking_message: Optional[list[str]] = None,
    references: Optional[dict[str, list[str]]] = None,
) -> commit.Link:
    return commit.Link(
        scope,
        summary,
        hash,
        hash[:7],
        breaking,
        breaking_message or [],
        references or {},
    )


def git_log(*commits: tuple[str, str], separator: str = "--SEP--") -> str:
    """
    Build output of ``git log --format=%h %H%n%B%n<separator>`` from
    ``(full_hash, message)`` pairs.
    """
    chunks = [f"{h[:7]} {h}\n{message}\n\n{separator}" for h, message in commits]
    return "\n".join(chunks) + "\n"
