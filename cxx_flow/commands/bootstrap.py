# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os

from cxx_flow.api.env import Runtime


def command_bootstrap(rt: Runtime):
    """Finishes bootstrapping on behalf of flow.py"""

    GITHUB_ENV = os.environ.get("GITHUB_ENV")
    if GITHUB_ENV is not None:
        with open(GITHUB_ENV, "a", encoding="UTF-8") as github_env:
            PATH = os.environ["PATH"]
            print(f"PATH={PATH}", file=github_env)
