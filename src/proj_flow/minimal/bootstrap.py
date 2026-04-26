# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.bootstrap** implements ``./flow bootstrap`` command.
"""

import importlib
import os
import subprocess
import sys
from typing import Annotated, cast

from proj_flow.api import arg, env


@arg.command("bootstrap")
def main(
    _ign: Annotated[
        bool,
        arg.FlagArgument(
            help="Bootstrap the Flow without virtual environment (usable with solutions like pyenv)",
            names=["--no-venv"],
        ),
    ],
    rt: env.Runtime,
):
    """Finish bootstrapping on behalf of flow.py"""

    GITHUB_ENV = os.environ.get("GITHUB_ENV")
    if GITHUB_ENV is not None:
        with open(GITHUB_ENV, "a", encoding="UTF-8") as github_env:
            PATH = os.environ["PATH"]
            print(f"PATH={PATH}", file=github_env)

    rt.message("Flow is now ready", level=env.Msg.ALWAYS)

    packages = set[str]()
    for name in cast(list[str], rt.items.get("extensions", [])):
        packages.add(name.split(".", 1)[0])

    packages.add("proj_flow")

    print_versions(rt, packages)


def get_versions() -> dict[str, str]:
    pip_run = cast(
        subprocess.CompletedProcess[bytes],
        subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            shell=False,
            capture_output=True,
        ),
    )
    if pip_run.returncode != 0:
        return {}

    output = pip_run.stdout.decode("utf-8").replace("\r\n", "\n").rstrip()
    versioned = [line.split("==", 1) for line in output.split("\n") if "==" in line]
    try:
        return {key.strip(): value.strip() for key, value in versioned}
    except ValueError:
        return {}


def get_version(name: str, versions: dict[str, str]):
    ver = versions.get(name)
    if not ver:
        name_dash = name.replace("_", "-")
        ver = versions.get(name_dash)
        if ver:
            return (name_dash, ver)
    if not ver:
        named_module = importlib.import_module(name).__dict__
        ver = named_module.get("__version__") or named_module.get("VERSION")
        if not isinstance(ver, str):
            ver = None
    if ver and ver.startswith("v"):
        ver = ver[1:]

    return (name, ver or "")


def print_versions(rt: env.Runtime, packages: set[str]):
    length = 0
    lines: list[tuple[str, str]] = []
    versions = get_versions()
    for name in sorted(packages):
        label, ver = get_version(name, versions)
        if length < len(label):
            length = len(label)
        if ver and ver.startswith("v"):
            ver = ver[1:]
        lines.append((label, f"v{ver}" if ver else "-"))

    rt.message("Dependencies:", level=env.Msg.STATUS)
    if not lines:
        rt.message("  <empty>", level=env.Msg.STATUS)
    for name, version in lines:
        rt.message(f"  {name:<{length}} {version}", level=env.Msg.STATUS)
