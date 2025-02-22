# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.python.rtdocs** defines RTDocs step (`"RTD"`), which uses
.readthedocs.yaml to build the HTML documentation.
"""

import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, cast

from proj_flow.api import env, step
from proj_flow.base import cmd


@step.register
class RTDocs:
    name = "RTD"

    def platform_dependencies(self):
        return ["python -m PyYAML"]

    def is_active(self, config: env.Config, rt: env.Runtime) -> bool:
        return os.path.isfile(os.path.join(rt.root, ".readthedocs.yaml"))

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        import venv

        import yaml

        with open(os.path.join(rt.root, ".readthedocs.yaml")) as rtd_yaml:
            data = yaml.load(rtd_yaml, Loader=yaml.Loader)

            formats = ["html"]

            build_jobs = cast(
                Dict[str, List[str]], data.get("build", {}).get("jobs", {})
            )

            sphinx_configuration = cast(
                Optional[str], data.get("sphinx", {}).get("configuration")
            )

            python_install = cast(
                List[Dict[str, Any]], data.get("python", {}).get("install", [])
            )

        builder: Optional[Builder] = None

        if sphinx_configuration:
            sphinx_configuration = os.path.join(rt.root, sphinx_configuration)
            builder = Sphinx(sphinx_configuration)

        READTHEDOCS_OUTPUT = (
            builder.READTHEDOCS_OUTPUT
            if builder is not None
            else os.path.join(rt.root, "docs/build")
        )
        os.environ["READTHEDOCS_OUTPUT"] = READTHEDOCS_OUTPUT
        os.environ["READTHEDOCS"] = "True"

        jobs: Dict[str, Callable[[], int]] = {
            "create_environment": lambda: _activate_virtual_env(
                venv, os.path.dirname(READTHEDOCS_OUTPUT)
            ),
        }
        if len(python_install):
            jobs["install"] = lambda: _install(python_install)

        if builder:
            for format in formats:
                jobs[f"build/{format}"] = builder.wrap(format)

        for name in build_jobs:
            if name != "build":
                jobs[name] = lambda: _script(build_jobs[name])
                continue

            build_jobs_build = cast(Dict[str, List[str]], build_jobs["build"])
            for format in formats:
                if format not in build_jobs_build:
                    continue
                jobs[f"build/{format}"] = lambda: _script(build_jobs_build[name])

        for job in _job_listing:
            try:
                impl = jobs[job]
            except KeyError:
                continue
            print(f"-- {job}")
            result = impl()
            if result:
                return 1
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


PYTHON_EXECUTABLE = sys.executable


def _python(
    *args: str,
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


def _pip(*args: str, capture_output: bool = False):
    return _python(*args, module="pip", capture_output=capture_output)


_build_targets = [
    "html",
    "htmlzip",
    "pdf",
    "epub",
]

_job_listing = [
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
    *(f"build/{tgt}" for tgt in _build_targets),
    "post_build",
]


def _get_venv_path(root: str):
    bindir = os.path.join(".venv", "bin")
    scripts = os.path.join(".venv", "Scripts")

    if os.path.isdir(os.path.join(root, bindir)):
        return bindir

    if os.path.isdir(os.path.join(root, scripts)):
        return scripts

    return None


def _activate_virtual_env(venv, root: str):
    global PYTHON_EXECUTABLE

    with cmd.cd(root):
        exec_ext = ".exe" if sys.platform == "win32" else ""
        python_exec = f"python{exec_ext}"
        bindir = _get_venv_path(root)
        has_venv = bindir is not None and os.path.isfile(
            os.path.join(bindir, python_exec)
        )

        if not has_venv:
            venv.create(".venv", with_pip=True, upgrade_deps=True)
            bindir = _get_venv_path(root)

        if bindir:
            PATH = f"{os.path.abspath(bindir)}{os.pathsep}{os.environ['PATH']}"
            os.environ["PATH"] = PATH
        PYTHON_EXECUTABLE = shutil.which("python") or sys.executable
    return 0


def _install(deps: List[Dict[str, Any]]):
    for dep in deps:
        try:
            requirements = dep["requirements"]
        except KeyError:
            continue

        result = _pip("install", "-q", "-r", requirements).returncode
        if result:
            return result
    return 0


def _script(calls: List[str]):
    for call in calls:
        result = subprocess.run(call, shell=True).returncode
        if result:
            return result
    return 0
