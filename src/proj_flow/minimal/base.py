# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.base** provides basic initialization setup for all
new projects.
"""

import sys

from proj_flow import __version__, api


class GitInit(api.init.InitStep):
    def priority(self):
        return sys.maxsize

    def platform_dependencies(self):
        return ["git"]

    def postprocess(self, rt: api.env.Runtime, context: dict):
        def git(*args):
            rt.cmd("git", *args)

        git("init")
        git("add", ".")
        git("commit", "-m", "Initial commit")


api.init.register_init_step(GitInit())
api.ctx.register_init_setting(
    api.ctx.Setting("__flow_version__", value=__version__),
    api.ctx.Setting("${", value="${"),
    project=None,
    is_hidden=True,
)
