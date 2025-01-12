# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from .. import __version__
from ..flow import config, ctx, init


class GitInit(init.InitStep):
    def platform_dependencies(self):
        return ["git"]

    def postprocess(self, rt: config.Runtime, context: dict):
        def git(*args):
            rt.cmd("git", *args)

        git("init")
        git("add", ".")
        git("commit", "-m", "Initial commit")


init.register_init_step(GitInit())
ctx.register_init_setting(
    ctx.Setting("__flow_version__", value=__version__),
    ctx.Setting("${", value="${"),
    is_hidden=True,
)
