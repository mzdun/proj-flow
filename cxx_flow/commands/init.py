# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import json
import os
import sys
from typing import Annotated, Optional

from cxx_flow import flow
from cxx_flow.api import arg, ctx, env, init


def command_init(
    path: Annotated[
        Optional[str],
        arg.Argument(
            help="location of initialized project; defaults to current directory",
            pos=True,
            default=".",
        ),
    ],
    non_interactive: Annotated[
        Optional[bool],
        arg.FlagArgument(help="selects all the default answers", names=["-y", "--yes"]),
    ],
    save_context: Annotated[
        Optional[bool],
        arg.FlagArgument(help="save the mustache context json", names=["--ctx"]),
    ],
    rt: env.Runtime,
):
    """Initializes a new project"""

    if path is not None:
        os.makedirs(path, exist_ok=True)
        os.chdir(path)

    errors = flow.dependency.verify(flow.dependency.gather(init.__steps))
    if len(errors) > 0:
        if not rt.silent:
            for error in errors:
                print(f"cxx-flow: {error}", file=sys.stderr)
        return 1

    context = flow.init.fixup(
        flow.init.all_default() if non_interactive else flow.interact.prompt()
    )
    if not non_interactive and not rt.silent:
        print()

    if save_context:
        with open(".context.json", "w", encoding="UTF-8") as jsonf:
            json.dump(context, jsonf, ensure_ascii=False, indent=4)

    flow.layer.copy_license(rt, context)
    if not rt.silent:
        print()

    layers = flow.layer.gather_package_layers(ctx.package_root, context)
    for fs_layer in layers:
        fs_layer.run(rt, context)

    if save_context:
        with open(".gitignore", "ab") as ignoref:
            ignoref.write("\n/.context.json\n".encode("UTF-8"))

    for step in init.__steps:
        step.postprocess(rt, context)
