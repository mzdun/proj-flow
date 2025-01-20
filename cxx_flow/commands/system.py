# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import platform
from typing import Annotated

from ..flow.arg import Argument
from ..flow.config import Runtime
from ..flow.uname import uname


def command_system(
    format: Annotated[
        str,
        Argument(
            help="select, what format should be returned",
            choices=["props", "platform", "debug"],
        ),
    ],
    _: Runtime,
):
    """Produces system information for CI pipelines"""

    node = platform.node()
    system, version, arch = uname()

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
            print(name, platform.__dict__[name]())

        print("-----")
        print(f"node {node}")
        print(f"os {system}")
        if version is not None:
            print(f"version {version}")
        print(f"machine {arch}")
