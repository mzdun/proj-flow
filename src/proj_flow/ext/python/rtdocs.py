# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.python.rtdocs** defines RTDocs step (`"RTD"`), which uses
.readthedocs.yaml to build the HTML documentation.
"""

import functools
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, cast

from proj_flow.api import env, step
from proj_flow.base import cmd


@dataclass
class RTDConfig:
    formats: List[str]
    build_jobs: Dict[str, List[str]]
    sphinx_configuration: Optional[str]
    python_install: List[Dict[str, Any]]
    builder: Optional["Builder"] = None
    readthedocs_output_path: str = ""

    @classmethod
    def load(cls, root: str):
        import yaml  # pylint: disable=import-outside-toplevel

        with open(os.path.join(root, ".readthedocs.yaml"), "rb") as rtd_yaml:
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

        builder: Optional["Builder"] = None
        if sphinx_configuration:
            sphinx_configuration = os.path.join(root, sphinx_configuration)
            builder = Sphinx(sphinx_configuration)

        readthedocs_output_path = (
            builder.readthedocs_output_path
            if builder is not None
            else os.path.join(root, "docs/build")
        )
        os.environ["READTHEDOCS_OUTPUT"] = readthedocs_output_path
        os.environ["READTHEDOCS"] = "True"

        return cls(
            formats=formats,
            build_jobs=build_jobs,
            sphinx_configuration=sphinx_configuration,
            python_install=python_install,
            builder=builder,
            readthedocs_output_path=readthedocs_output_path,
        )

    def jobs(self):
        import venv  # pylint: disable=import-outside-toplevel

        jobs: Dict[str, Callable[[], int]] = {
            "create_environment": lambda: _activate_virtual_env(
                venv, os.path.dirname(self.readthedocs_output_path)
            ),
        }
        if self.python_install:
            jobs["install"] = lambda: _install(self.python_install)

        if self.builder:
            for fmt in self.formats:
                jobs[f"build/{fmt}"] = self.builder.wrap(fmt)

        for name in self.build_jobs:
            if name != "build":
                jobs[name] = functools.partial(_script, self.build_jobs[name])
                continue

            build_jobs_build = cast(Dict[str, List[str]], self.build_jobs["build"])
            for fmt in self.formats:
                if fmt not in build_jobs_build:
                    continue
                jobs[f"build/{fmt}"] = functools.partial(
                    _script, build_jobs_build[name]
                )

        return jobs


@step.register
class RTDocs:
    name = "RTD"

    def platform_dependencies(self):
        return ["python -m PyYAML"]

    def is_active(self, _config: env.Config, rt: env.Runtime) -> bool:
        return os.path.isfile(os.path.join(rt.root, ".readthedocs.yaml"))

    def run(self, _config: env.Config, rt: env.Runtime) -> int:
        jobs = RTDConfig.load(rt.root).jobs()

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
    def readthedocs_output_path(self) -> str: ...

    @abstractmethod
    def build(self, target: str) -> int: ...

    def wrap(self, target: str) -> Callable[[], int]:
        return lambda: self.build(target)


class Sphinx(Builder):
    readthedocs_output_path: str = ""

    def __init__(self, config: str):
        self.config = config
        self.source = os.path.dirname(config)
        self.readthedocs_output_path = os.path.join(
            os.path.dirname(self.source), "build"
        )

    def build(self, target: str):
        builder = "latex" if target == "pdf" else target
        return subprocess.run(
            ["sphinx-build", "-M", builder, self.source, self.readthedocs_output_path],
            check=False,
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
            check=False,
            capture_output=capture_output,
        )
    return subprocess.run(
        [PYTHON_EXECUTABLE, *args], check=False, capture_output=capture_output
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
            path = f"{os.path.abspath(bindir)}{os.pathsep}{os.environ['PATH']}"
            os.environ["PATH"] = path
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
        result = subprocess.run(call, shell=True, check=False).returncode
        if result:
            return result
    return 0
