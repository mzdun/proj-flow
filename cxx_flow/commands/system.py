# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import platform
import shlex
from pprint import pprint
from typing import Annotated

from ..flow.arg import Argument
from ..flow.config import Runtime


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
    """Produce system information for CI pipelines"""

    node = platform.node()
    uname = platform.uname()

    system = uname.system.lower()
    machine = uname.machine
    version = uname.version

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

    system_nt = system.split("_nt-", 1)
    if len(system_nt) > 1:
        system = system_nt[0]
        version = None
    elif system == "windows":
        machine = "x86_64" if machine.lower() == "amd64" else "x86_32"
        version = None
    elif system == "linux":
        os_release = _os_release()
        system = os_release.get("ID", system)
        version = os_release.get("VERSION_ID", version)

        if system[:9] == "opensuse-":
            system = "opensuse"
        if system == "arch":
            version = None

        if format == "debug":
            print("-----")
            pprint(os_release)


    if format == "props":
        print(f"-phost.name='{node}'")
        print(f"-pos='{system}'")
        if version is not None:
            print(f"-pos.version='{version}'")
        print(f"-parch='{machine}'")

    if format == "platform":
        version = "" if version is None else f"-{version}"
        print(f"{system}{version}-{machine}")

    if format == "debug":
        print("-----")
        print(f"node {node}")
        print(f"os {system}")
        if version is not None:
            print(f"version {version}")
        print(f"machine {machine}")

def _os_release():
    for file in ["/etc/os-release", "/usr/lib/os-release"]:
        try:
            result = {}
            with open(file) as f:
                for line in f:
                    var = line.strip().split("=", 1)
                    if len(var) < 2:
                        continue
                    name, value = (val.strip() for val in var)
                    value = " ".join(shlex.split(value))
                    result[name] = value
            return result
        except FileNotFoundError:
            pass
        return {}

