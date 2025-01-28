# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import platform
import sys
from typing import Annotated

from cxx_flow.api import arg, env
from cxx_flow.base import uname


def command_system(
    format: Annotated[
        str,
        arg.Argument(
            help="select, what format should be returned",
            choices=["props", "platform", "debug"],
        ),
    ],
    _: env.Runtime,
):
    """Produces system information for CI pipelines"""

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
