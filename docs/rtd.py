#!/usr/bin/env python3

# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
import shutil
import subprocess
import sys
import venv
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, cast

try:
    import yaml
except ModuleNotFoundError:
    print("This script needs PyYAML pre-installed", file=sys.stderr)
    sys.exit(1)

PYTHON_EXECUTABLE = sys.executable


def python(
    *args: List[str],
    module: Optional[str] = None,
    capture_output: bool = True,
) -> subprocess.CompletedProcess:
    if module is not None:
        return subprocess.run(
            [PYTHON_EXECUTABLE, "-m", module, *args],
            shell=False,
            capture_output=capture_output,
        )
    return subprocess.run(
        [PYTHON_EXECUTABLE, *args], shell=False, capture_output=capture_output
    )


def pip(*args: List[str], capture_output: bool = False):
    return python(*args, module="pip", capture_output=capture_output)


build_targets = [
    "html",
    "htmlzip",
    "pdf",
    "epub",
]

job_listing = [
    # "post_checkout",
    # "pre_system_dependencies",
    # "post_system_dependencies",
    "pre_create_environment",
    "create_environment",
    "post_create_environment",
    "pre_install",
    "install",
    "post_install",
    "pre_build",
    *(f"build/{tgt}" for tgt in build_targets),
    "post_build",
]


ROOT_DIR = os.path.abspath(os.path.join(__file__, "../.."))


@contextmanager
def cd(path: str):
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)


def get_venv_path():
    bindir = os.path.join(".venv", "bin")
    scripts = os.path.join(".venv", "Scripts")

    if os.path.isdir(bindir):
        return bindir

    if os.path.isdir(scripts):
        return scripts

    return None


def activate_virtual_env():
    global PYTHON_EXECUTABLE

    with cd(os.path.dirname(__file__)):
        exec_ext = ".exe" if sys.platform == "win32" else ""
        python_exec = f"python{exec_ext}"
        bindir = get_venv_path()
        has_venv = bindir is not None and os.path.isfile(
            os.path.join(bindir, python_exec)
        )

        if not has_venv:
            venv.create(".venv", with_pip=True, upgrade_deps=True)
            bindir = get_venv_path()

        os.environ["PATH"] = (
            f"{os.path.abspath(bindir)}{os.pathsep}{os.environ['PATH']}"
        )
        PYTHON_EXECUTABLE = shutil.which("python") or sys.executable

    return 0


with open(os.path.join(ROOT_DIR, ".readthedocs.yaml")) as rtd_yaml:
    data = yaml.load(rtd_yaml, Loader=yaml.Loader)

    formats = cast(List[str], data.get("formats", []))
    formats.insert(0, "html")

    build_jobs = cast(
        Optional[Dict[str, List[str]]], data.get("build", {}).get("jobs", {})
    )

    sphinx_configuration = cast(
        Optional[str], data.get("sphinx", {}).get("configuration")
    )

    python_install = cast(
        List[Dict[str, Any]], data.get("python", {}).get("install", [])
    )


def install(deps: List[Dict[str, Any]]):
    for dep in deps:
        try:
            requirements = dep["requirements"]
        except KeyError:
            continue

        result = pip("install", "-q", "-r", requirements).returncode
        if result:
            return result
    return 0


def script(calls: List[str]):
    for call in calls:
        result = subprocess.run(call, shell=True).returncode
        if result:
            return result
    return 0


class Builder(ABC):
    @property
    @abstractmethod
    def READTHEDOCS_OUTPUT(self) -> str: ...

    @abstractmethod
    def build(self, target: str) -> int: ...

    def wrap(self, target: str) -> Callable[[], int]:
        return lambda: self.build(target)


class Sphinx(Builder):
    READTHEDOCS_OUTPUT: str = ""

    def __init__(self, config: str):
        self.config = config
        self.source = os.path.dirname(config)
        self.READTHEDOCS_OUTPUT = os.path.join(os.path.dirname(self.source), "build")

    def build(self, target: str):
        builder = "latex" if target == "pdf" else target
        return subprocess.run(
            ["sphinx-build", "-M", builder, self.source, self.READTHEDOCS_OUTPUT],
            shell=False,
        ).returncode


jobs: Dict[str, Callable[[], int]] = {"create_environment": activate_virtual_env}
if len(python_install):
    jobs["install"] = lambda: install(python_install)

builder: Optional[Builder] = None

if sphinx_configuration:
    builder = Sphinx(sphinx_configuration)

if builder:
    for format in formats:
        jobs[f"build/{format}"] = builder.wrap(format)

for name in build_jobs:
    if name != "build":
        jobs[name] = lambda: script(build_jobs[name])
        continue

    build_jobs_build = cast(Dict[str, Dict[str, List[str]]], build_jobs["build"])
    for format in formats:
        if format not in build_jobs_build:
            continue
        jobs[f"build/{format}"] = lambda: script(build_jobs_build[name])


READTHEDOCS_OUTPUT = builder.READTHEDOCS_OUTPUT if builder is not None else "docs/build"
os.environ["READTHEDOCS_OUTPUT"] = READTHEDOCS_OUTPUT

for job in job_listing:
    try:
        impl = jobs[job]
    except KeyError:
        continue
    print(f"-- {job}")
    result = impl()
    if result:
        sys.exit(1)
