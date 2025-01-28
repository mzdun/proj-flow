# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import argparse
import json
import os
import sys
from typing import Annotated, Optional

from cxx_flow.api import arg, env
from cxx_flow.flow.configs import Configs


@arg.flow_subcommand
def matrix(
    official: Annotated[
        Optional[bool], arg.FlagArgument(help="cut matrix to minimal set of builds")
    ],
    rt: env.Runtime,
):
    """Supplies data for github actions"""

    configs = Configs(
        rt, argparse.Namespace(configs=[], matrix=True, official=official)
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
