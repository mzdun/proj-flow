# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.base** provides basic initialization setup for all
new projects.
"""

import sys
from typing import List

from proj_flow import __version__, api
from proj_flow.flow import layer


class GitInit(api.init.InitStep):
    layers: List[layer.LayerInfo] = []

    def priority(self):
        return sys.maxsize

    def platform_dependencies(self):
        return ["git"]

    def postprocess(self, rt: api.env.Runtime, context: dict):
        def git(*args):
            rt.cmd("git", *args)

        git("init")
        git("add", ".")

        executables: List[str] = []

        for fs_layer in GitInit.layers:
            for info in fs_layer.get_git_checks():
                if info.is_executable:
                    executables.append(info.dst)

        if len(executables):
            git("update-index", "--chmod=+x", *executables)

        git("commit", "-m", "Initial commit")


api.init.register_init_step(GitInit())
api.ctx.register_init_setting(
    api.ctx.Setting("__flow_version__", value=__version__),
    api.ctx.Setting("${", value="${"),
    project=None,
    is_hidden=True,
)
