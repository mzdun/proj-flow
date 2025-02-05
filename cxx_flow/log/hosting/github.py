# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.log.hosting.github** builds a log message for GiHub Releases.
"""

import json
from pprint import pformat
from typing import Any, List, NamedTuple, Optional, Tuple, cast

from cxx_flow.api import env
from cxx_flow.base import cmd
from cxx_flow.log import commit, release


class _GitHub(NamedTuple):
    remote: str
    owner: str
    repo: str


_NO_GITHUB = _GitHub("", "", "")


class GitHub(commit.Hosting):
    """
    Generates links to GitHub.
    """

    _info: _GitHub
    rt: env.Runtime

    def __init__(self, info: _GitHub, rt: env.Runtime):
        super().__init__(f"https://github.com/{info.owner}/{info.repo}")
        self._info = info
        self.rt = rt

    @property
    def is_active(self):
        return not not self._info.remote

    @property
    def remote(self):
        return self._info.remote

    @property
    def owner(self):
        return self._info.owner

    @property
    def repo(self):
        return self._info.repo

    @property
    def root(self):
        return f"/repos/{self.owner}/{self.repo}"

    def single_commit_link(self, link: commit.Link) -> Optional[str]:
        return f"{self.host_link}/commit/{link.hash}"

    def commit_listing_link(self, setup: commit.LogSetup) -> Optional[str]:
        curr_tag = setup.curr_tag or "HEAD"
        if not setup.prev_tag:
            return f"{self.host_link}/commits/{curr_tag}"

        return f"{self.host_link}/compare/{setup.prev_tag}...{curr_tag}"

    def reference_link(self, ref: str) -> Optional[str]:
        if ref[:1] == "#" and ref[1:].isdigit():
            f"{self.host_link}/issues/{ref[1:]}"

        return None

    def gh(
        self,
        res: str,
        *args: str,
        method: Optional[str] = None,
        capture_output: bool = True,
        **kwargs,
    ):
        url = f"{self.root}{res}"
        accept = kwargs.get("accept", "application/vnd.github+json")
        call = [
            "gh",
            "api",
            "-H",
            f"Accept: {accept}",
            "-H",
            "X-GitHub-Api-Version: 2022-11-28",
        ]
        if method:
            call.extend(["--method", method.upper()])

        if capture_output:
            if self.rt.dry_run:
                self.rt.print(*call, url, *args)
                return None
            return self.rt.capture(*call, url, *args)

        self.rt.print(*call, url, *args)
        if self.rt.dry_run:
            return None
        return cmd.run(*call, url, *args)

    def json_from(
        self,
        res: str,
        *args: str,
        method: Optional[str] = None,
        server: Optional[str] = None,
        default: Any = {},
    ):
        proc = self.gh(res, *args, method=method, server=server)
        if proc is None:
            return default

        if self.rt.verbose:
            self.rt.message("[DEBUG] stdout=")
            self.rt.message(pformat(json.loads(proc.stdout)))

        return json.loads(proc.stdout)

    def draft_a_release(
        self, log: commit.ChangeLog, setup: commit.LogSetup, git: commit.Git
    ) -> commit.ReleaseInfo:
        if setup.curr_tag is None:
            git.rt.fatal(f"New tag is needed.")

        git.push_with_refs(self.remote, "main")

        body = release.ReleaseMessage(setup).format_changelog(log)

        rel = {
            "tag_name": setup.curr_tag,
            "name": setup.curr_tag,
            "body": body,
            "draft": True,
            "prerelease": len(setup.curr_tag.split("-", 1)) > 1,
        }

        flags: List[str] = []
        for name, value in rel.items():
            is_str = isinstance(value, str)
            if not is_str:
                value = json.dumps(value)
            flags.append("-f" if is_str else "-F")
            flags.append(f"{name}={value}")

        data = self.json_from("/releases", *flags, method="POST", default={})
        html_url = cast(Optional[str], data.get("html_url"))

        return commit.ReleaseInfo(draft_url=html_url)

    @staticmethod
    def from_repo(git: commit.Git, remote: Optional[str] = None):
        info = _find_github(git, remote)
        if info == _NO_GITHUB:
            return commit.NoHosting()
        return GitHub(info, git.rt)


SSH_PREFIX = "git@github.com:"
HTTPS_PREFIX = "https://github.com/"
GIT_SUFFIX = ".git"
_NO_REPO = "", ""


def _repo_from_gh_cli(git: commit.Git) -> Tuple[str, str]:
    gh = cmd.which("gh")
    if gh is None:
        return _NO_REPO
    proc = git.rt.capture("gh", "repo", "view", "--json", "name,owner", silent=True)
    if proc.returncode != 0:
        return _NO_REPO
    data = json.loads(proc.stdout)
    repo: Optional[str] = data.get("name")
    org: Optional[str] = data.get("owner", {}).get("login")
    if org and repo:
        return org, repo
    return _NO_REPO


def _repo_from_url(url: str):
    for prefix in [SSH_PREFIX, HTTPS_PREFIX]:
        if not url.startswith(prefix):
            continue

        project_path = url[len(prefix) :]
        if project_path.endswith(GIT_SUFFIX):
            project_path = project_path[: -len(GIT_SUFFIX)]

        chunks = project_path.split("/", 1)
        if len(chunks) == 2:
            org, repo = chunks
            return org, repo

    return _NO_REPO


def _github_from_gh(
    gh_repo: Tuple[str, str], remotes: List[commit.Remote], remote_hint: Optional[str]
):
    if gh_repo == _NO_REPO:
        return _NO_GITHUB

    kept_answer = _NO_GITHUB
    for name, _, url in remotes:
        url_repo = _repo_from_url(url)
        if url_repo != gh_repo:
            continue

        candidate = _GitHub(remote=name, owner=url_repo[0], repo=url_repo[1])
        if remote_hint and remote_hint != name:
            kept_answer = candidate
            continue
        return candidate

    return kept_answer


def _github_from_remotes(remotes: List[commit.Remote], remote_hint: Optional[str]):
    kept_answer = _NO_GITHUB
    for name, _, url in remotes:
        url_repo = _repo_from_url(url)
        if url_repo == _NO_REPO:
            continue

        candidate = _GitHub(remote=name, owner=url_repo[0], repo=url_repo[1])
        if remote_hint and remote_hint != name:
            kept_answer = candidate
            continue
        return candidate

    return kept_answer


def _find_github(git: commit.Git, remote_hint: Optional[str]) -> _GitHub:
    gh_repo = _repo_from_gh_cli(git)
    remotes = list(git.remotes(silent=True))

    candidate = _github_from_gh(gh_repo, remotes, remote_hint)

    if candidate != _NO_GITHUB:
        return candidate

    return _github_from_remotes(remotes, remote_hint)
