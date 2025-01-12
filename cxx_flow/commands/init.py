# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import json
import os
import sys
from typing import Annotated, Optional

from ..flow import config, ctx, dependency, init
from ..flow.arg import Argument, FlagArgument
from ..flow.interact import prompt
from ..flow.layer import copy_license, gather_package_layers


def command_init(
    path: Annotated[
        Optional[str],
        Argument(
            help="location of initialized project; defaults to current directory",
            pos=True,
            default=".",
        ),
    ],
    non_interactive: Annotated[
        Optional[bool],
        FlagArgument(help="selects all the default answers", names=["-y", "--yes"]),
    ],
    save_context: Annotated[
        Optional[bool],
        FlagArgument(help="save the mustache context json", names=["--ctx"]),
    ],
    rt: config.Runtime,
):
    """Initializes a new project"""

    if path is not None:
        os.makedirs(path, exist_ok=True)
        os.chdir(path)

    errors = dependency.verify(dependency.gather(init.__steps))
    if len(errors) > 0:
        if not rt.silent:
            for error in errors:
                print(f"cxx-flow: {error}", file=sys.stderr)
        return 1

    context = ctx.fixup(ctx.all_default() if non_interactive else prompt())
    if not non_interactive and not rt.silent:
        print()

    if save_context:
        with open(".context.json", "w", encoding="UTF-8") as jsonf:
            json.dump(context, jsonf, ensure_ascii=False, indent=4)

    copy_license(rt, context)
    if not rt.silent:
        print()

    layers = gather_package_layers(ctx.package_root, context)
    for layer in layers:
        layer.run(rt, context)

    for step in init.__steps:
        step.postprocess(rt, context)
