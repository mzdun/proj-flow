# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.init** implements ``proj-flow init`` command.
"""

import json
import os
import sys
from typing import Annotated, Optional

import yaml

from proj_flow import dependency, flow
from proj_flow.api import arg, ctx, env, init
from proj_flow.base.name_list import name_list
from proj_flow.project import api, interact


def _project_types():
    return list(map(lambda proj: proj.id, api.project_type.get()))


def _project_help():
    return (
        "Type of project to create. "
        f"Allowed values are: {name_list(_project_types())}"
    )


@arg.command("init")
def main(
    project: Annotated[
        str,
        arg.Argument(
            help=_project_help,
            meta="project",
            pos=True,
            choices=_project_types,
        ),
    ],
    path: Annotated[
        Optional[str],
        arg.Argument(
            help="Location of initialized project. "
            "The directory will be created, if it does not exist yet. "
            "Defaults to current directory.",
            pos=True,
            default=".",
        ),
    ],
    non_interactive: Annotated[
        bool,
        arg.FlagArgument(help="Selects all the default answers", names=["-y", "--yes"]),
    ],
    save_context: Annotated[
        bool,
        arg.FlagArgument(help="Save the mustache context as JSON", names=["--ctx"]),
    ],
    rt: env.Runtime,
):
    """Initialize new project"""

    try:
        current_project = api.get_project_type(project)
    except api.ProjectNotFound:
        print(f"proj-flow init: error: project type `{project}` is not known")
        return 1

    if path is not None:
        os.makedirs(path, exist_ok=True)
        os.chdir(path)

    errors = dependency.verify(dependency.gather(init.__steps))
    if len(errors) > 0:
        if not rt.silent:
            for error in errors:
                print(f"proj-flow: {error}", file=sys.stderr)
        return 1

    context = current_project.get_context(not non_interactive, rt)
    if not non_interactive and not rt.silent:
        print()

    if save_context and rt.verbose:
        lines = yaml.dump(context, indent=4).rstrip().split("\n")
        for line in lines:
            rt.message("[CONTEXT]", line)

    if save_context and not rt.dry_run:
        with open(".context.yaml", "w", encoding="UTF-8") as jsonf:
            yaml.dump(context, jsonf, indent=4)

    flow.layer.copy_license(rt, context)
    if not rt.silent:
        print()

    layers = flow.layer.gather_package_layers(ctx.package_root, context)
    for fs_layer in layers:
        fs_layer.run(rt, context)

    if save_context and not rt.dry_run:
        with open(".gitignore", "ab") as ignoref:
            ignoref.write("\n/.context.yaml\n".encode("UTF-8"))

    current_project.append_extensions(context)

    steps = sorted((step.priority(), i, step) for i, step in enumerate(init.__steps))
    for _, _, step in steps:
        step.postprocess(rt, context)
