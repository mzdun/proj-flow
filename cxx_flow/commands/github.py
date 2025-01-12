# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import json
import os
import sys
from typing import Annotated, Optional

from ..flow.arg import FlagArgument
from ..flow.config import Configs, Runtime


def command_github(
    matrix: Annotated[Optional[bool], FlagArgument(help="print matrix json")],
    configs: Configs,
    rt: Runtime,
):
    """Supplies data for github actions"""

    if matrix:
        usable = [usable.items for usable in configs.usable]
        if "GITHUB_ACTIONS" in os.environ:
            var = json.dumps({"include": usable})
            print(f"matrix={var}")
        else:
            json.dump(usable, sys.stdout)
        return

    print("cxx-flow github", matrix, configs)
