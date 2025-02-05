# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.plugins.commands.ci.changelog** implements
``./flow ci changelog`` command.
"""

import typing

from cxx_flow.api import arg, env
from cxx_flow.log import commit, hosting, rich_text


@arg.command("ci", "changelog")
def main(
    rt: env.Runtime,
    rst: typing.Annotated[
        bool,
        arg.FlagArgument(help="Use reStructuredText instead of Markdown."),
    ],
    rebuild: typing.Annotated[
        bool,
        arg.FlagArgument(
            help="Recreate entire changelog. Useful, when adapting existing project."
        ),
    ],
    all: typing.Annotated[
        bool, arg.FlagArgument(help="Take all Conventional Commits.")
    ],
):
    generator = rich_text.select_generator(rst=rst)

    git = commit.Git(rt)
    tags = git.tag_list()
    gh_links = hosting.github.GitHub.from_repo(git)

    if rebuild:
        generator.create_changelog(tags, git, gh_links, rt, take_all=all)
        return 0

    prev_tag = tags[-2] if len(tags) > 1 else None
    curr_tag = tags[-1] if len(tags) > 0 else None

    setup = commit.LogSetup(gh_links, prev_tag, curr_tag, take_all=all)
    log, _ = git.get_log(setup)
    generator.update_changelog(log, setup, rt)
