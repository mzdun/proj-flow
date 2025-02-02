# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.commands.bootstrap** implements ``./flow bootstrap`` command.
"""

import os

from cxx_flow.api import arg, env


@arg.command("bootstrap")
def command_bootstrap(rt: env.Runtime):
    """Finish bootstrapping on behalf of flow.py"""

    GITHUB_ENV = os.environ.get("GITHUB_ENV")
    if GITHUB_ENV is not None:
        with open(GITHUB_ENV, "a", encoding="UTF-8") as github_env:
            PATH = os.environ["PATH"]
            print(f"PATH={PATH}", file=github_env)
