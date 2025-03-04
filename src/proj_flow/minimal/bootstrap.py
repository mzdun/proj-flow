# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.bootstrap** implements ``./flow bootstrap`` command.
"""

import os

from proj_flow.api import arg


@arg.command("bootstrap")
def main():
    """Finish bootstrapping on behalf of flow.py"""

    github_env_path = os.environ.get("GITHUB_ENV")
    if github_env_path is not None:
        with open(github_env_path, "a", encoding="UTF-8") as github_env:
            path = os.environ["PATH"]
            print(f"PATH={path}", file=github_env)
