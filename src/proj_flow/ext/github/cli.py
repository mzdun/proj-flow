# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.github.cli** adds the ``github`` command, replacing the
old ``ci`` code. Additionally, it provides ``github matrix`` and ``github
release`` commands. It will soon also have ``github publish``, finishing the
job started in ``release``.
"""

import argparse
import json
import os
import sys
import typing

from proj_flow import log
from proj_flow.api import arg, env, release
from proj_flow.base.name_list import name_list
from proj_flow.ext.github import publishing
from proj_flow.flow.configs import Configs
from proj_flow.log import commit, hosting, rich_text

FORCED_LEVEL_CHOICES = list(commit.FORCED_LEVEL.keys())


@arg.command("github")
def github():
    """Interact with GitHub workflows and releases"""


@arg.command("github", "matrix")
def matrix(
    official: typing.Annotated[
        bool, arg.FlagArgument(help="Cut matrix to release builds only")
    ],
    rt: env.Runtime,
):
    """Supply data for GitHub Actions"""

    configs = Configs(
        rt,
        argparse.Namespace(configs=[], matrix=True, official=official),
        expand_compilers=False,
    )

    usable = [usable.items for usable in configs.usable]
    for config in usable:
        if "--orig-compiler" in config:
            orig_compiler = config["--orig-compiler"]
            del config["--orig-compiler"]
            config["compiler"] = orig_compiler

    if "GITHUB_ACTIONS" in os.environ:
        var = json.dumps({"include": usable})
        GITHUB_OUTPUT = os.environ.get("GITHUB_OUTPUT")
        if GITHUB_OUTPUT is not None:
            with open(GITHUB_OUTPUT, "a", encoding="UTF-8") as github_output:
                print(f"matrix={var}", file=github_output)
        else:
            print(f"matrix={var}")
    else:
        json.dump(usable, sys.stdout)


@arg.command("github", "release")
def release_cmd(
    rt: env.Runtime,
    all: typing.Annotated[
        bool, arg.FlagArgument(help="Take all Conventional Commits.")
    ],
    force: typing.Annotated[
        typing.Optional[str],
        arg.Argument(
            help="Ignore the version change from changelog and instead use this value. "
            f"Allowed values are: {name_list(FORCED_LEVEL_CHOICES)}.",
            meta="level",
            choices=FORCED_LEVEL_CHOICES,
        ),
    ],
    publish: typing.Annotated[
        typing.Optional[str],
        arg.Argument(
            help="Publish the release during this command.",
            choices=["ON", "OFF"],
        ),
    ],
):
    """
    Bump the project version based on current git logs, create a "chore"
    commit for the change, attach an annotated tag with the version number
    and push it all to GitHub.
    """

    generator = (
        rich_text.api.changelog_generators.first()
        or rich_text.markdown.ChangelogGenerator()
    )
    forced_level = commit.FORCED_LEVEL.get(force) if force else None
    git = commit.Git(rt)
    gh_links = hosting.github.GitHub.from_repo(git) or commit.NoHosting()
    released = False

    try:
        next_tag = log.release.add_release(
            rt=rt,
            forced_level=forced_level,
            take_all=all,
            draft=publish != "ON",
            generator=generator,
            git=git,
            hosting=gh_links,
        )
        released = not not next_tag
    except log.release.VersionNotAdvancing as err:
        rt.message(err.message, level=env.Msg.STATUS)
        return
    except log.error.ReleaseError as err:
        rt.fatal(err.message)
    finally:
        if "GITHUB_ACTIONS" in os.environ:
            GITHUB_OUTPUT = os.environ.get("GITHUB_OUTPUT")
            if GITHUB_OUTPUT is not None:
                with open(GITHUB_OUTPUT, "a", encoding="UTF-8") as github_output:
                    print(f"tag={next_tag}", file=github_output)
                    print(f"released={json.dumps(released)}", file=github_output)


@arg.command("github", "publish")
def publish(
    rt: env.Runtime,
    ref: typing.Annotated[
        typing.Optional[str],
        arg.Argument(
            help="Publish this release draft. In case this is called from within "
            "GitHub Actions and your release is named exactly like the tag used to "
            "trigger this flow, you can use ${{github.action_ref}} variable. "
            "Defaults to current tag.",
            meta="release",
        ),
    ],
    upload: typing.Annotated[
        typing.Optional[str],
        arg.Argument(
            help="If present, upload files from the directory to the referenced "
            "release before publishing.",
            meta="directory",
        ),
    ],
):
    """
    Upload package artifacts to a GitHub release and in case the release
    is still in draft, publish it.
    """

    git = commit.Git(rt)
    gh_links = hosting.github.GitHub.from_repo(git) or commit.NoHosting()
    project = release.get_project(rt)

    tag_name = ref or project.tag_name

    release_info = gh_links.locate_release(tag_name)
    if release_info is None and not rt.dry_run:
        rt.fatal(f"No release matches {tag_name}")

    if upload is not None:
        matcher = publishing.build_regex(project)
        directory, names = publishing.gather_artifacts(upload, matcher)
        if not len(names):
            rt.fatal(f"No artifact matches {matcher.pattern}")

        publishing.checksums(rt, directory, names, "sha256sum.txt")

        if release_info is not None:
            gh_links.upload_to_release(release_info, directory, names)
        else:
            rt.message(f"Would upload:", level=env.Msg.STATUS)
            for name in names:
                rt.message(f"  * {name}", level=env.Msg.STATUS)

    if release_info is not None:
        info = gh_links.publish(release_info)
        if info.url:
            msg = "Visit draft at" if info.is_draft else "Visit release at"
            rt.message(msg, info.url, level=env.Msg.ALWAYS)
