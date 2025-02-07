# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.github.hosting** adds GitHub hosting environment.
"""

from typing import Optional

from proj_flow.log import commit
from proj_flow.log.hosting.github import GitHub


@commit.hosting_factories.add
class Plugin(commit.HostingFactory):
    def from_repo(
        self, git: commit.Git, remote: Optional[str] = None
    ) -> Optional[commit.Hosting]:
        return GitHub.from_repo(git, remote)
