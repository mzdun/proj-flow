# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.system** implements ``./flow system`` command.
"""

import platform
import sys
from typing import Annotated

from proj_flow.api import arg
from proj_flow.base import uname


@arg.command("system")
def main(
    format: Annotated[
        str,
        arg.Argument(
            help="Select, what format should be returned",
            choices=["props", "platform", "debug"],
        ),
    ],
):
    """Produce system information for CI pipelines"""

    node = platform.node()
    system, version, arch = uname.uname()

    if format == "props":
        print(f"-phost.name='{node}'")
        print(f"-pos='{system}'")
        if version is not None:
            print(f"-pos.version='{version}'")
        print(f"-parch='{arch}'")

    if format == "platform":
        version = "" if version is None else f"-{version}"
        print(f"{system}{version}-{arch}")

    if format == "debug":
        for name in [
            "uname",
            "machine",
            "node",
            "platform",
            "processor",
            "release",
            "system",
            "version",
        ]:
            print(name, platform.__dict__[name](), file=sys.stderr)

        print("-----", file=sys.stderr)
        print(f"node {node}", file=sys.stderr)
        print(f"os {system}", file=sys.stderr)
        if version is not None:
            print(f"version {version}", file=sys.stderr)
        print(f"machine {arch}", file=sys.stderr)
