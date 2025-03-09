# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import argparse
import collections
import platform
from dataclasses import dataclass

import pytest

from proj_flow import __version__, dependency
from proj_flow.api import env

from .capture import Capture
from .load_flow_cfg import load_flow_cfg


@pytest.fixture
def flow_cfg(mocker):
    return load_flow_cfg(mocker, user_cfg=None, proj_cfg=None)


def _args(**kwargs):
    return argparse.Namespace(**kwargs)


DepTest = collections.namedtuple("DepTest", ["version", "expression", "expected"])

TESTS: list[DepTest] = [
    DepTest("3.14", "==2.71", "test-mod: version `3.14` does not match `==2.71`"),
    DepTest("3.14", ">=2.71", None),
    DepTest("2.71", ">=3.14", "test-mod: version `2.71` does not match `>=3.14`"),
    DepTest("3.14", "<=2.71", "test-mod: version `3.14` does not match `<=2.71`"),
    DepTest("2.71", "<=3.14", None),
    DepTest("2.0.0", "~=1", "test-mod: version `2.0.0` does not match `~=1`"),
    DepTest("2.6.0", "~=2", None),
    DepTest("2.6.0", ",~=1.0", "test-mod: version `2.6.0` does not match `~=1.0`"),
    DepTest("2.6.1", "~=2.6,!=2.6.5", None),
    DepTest(
        "2.6.5", "~=2.6,!=2.6.5", "test-mod: version `2.6.5` does not match `!=2.6.5`"
    ),
    DepTest("3.14", ">2.71", None),
    DepTest("3.14", ">3.14", "test-mod: version `3.14` does not match `>3.14`"),
    DepTest("2.71", "<2.71", "test-mod: version `2.71` does not match `<2.71`"),
    DepTest("2.71", "<3.14", None),
]


@pytest.mark.parametrize(["version", "expression", "expected"], TESTS)
def test_deps(version: str, expression: str, expected: str | bool):
    dep = dependency.Dependency("test-mod", expression)
    actual = dep.match_version(version)
    assert actual == expected


@dataclass
class StepLike:
    deps: list[str]

    def platform_dependencies(self):
        return self.deps


# pylint: disable-next=redefined-outer-name
def test_gather_no_steps(flow_cfg: env.FlowConfig):
    rt = env.Runtime.from_flow_cfg(flow_cfg)
    steps: list[StepLike] = []

    sys_exit_called = False
    with Capture() as capture:
        try:
            dependency.verify(dependency.gather(steps), rt)
        except SystemError:
            sys_exit_called = True

    assert not sys_exit_called
    assert capture.stderr == ""
    assert capture.stdout == ""


# pylint: disable-next=redefined-outer-name
def test_gather_empty_steps(flow_cfg: env.FlowConfig):
    rt = env.Runtime.from_flow_cfg(flow_cfg)
    steps: list[StepLike] = [
        StepLike([]),
        StepLike([]),
        StepLike([]),
        StepLike([]),
    ]

    sys_exit_called = False
    with Capture() as capture:
        try:
            dependency.verify(dependency.gather(steps), rt)
        except SystemError:
            sys_exit_called = True

    assert not sys_exit_called
    assert capture.stderr == ""
    assert capture.stdout == ""


# pylint: disable-next=redefined-outer-name
def test_gather_python(flow_cfg: env.FlowConfig):
    rt = env.Runtime.from_flow_cfg(flow_cfg)
    steps: list[StepLike] = [
        StepLike([f"python ~= {platform.python_version()}"]),
        StepLike(["python -m pip"]),
        StepLike([f"python -m proj_flow=={__version__}"]),
    ]

    sys_exit_called = False
    with Capture() as capture:
        try:
            dependency.verify(dependency.gather(steps), rt)
        except SystemError:
            sys_exit_called = True

    assert not sys_exit_called
    assert capture.stderr == ""
    assert capture.stdout == ""


Pipe = collections.namedtuple("Pipe", ["returncode", "stdout", "stderr"])


# pylint: disable-next=unused-argument
def _faux_run(app: str, *args: str, capture_output=False):
    if app == "angry":
        return Pipe(returncode=1, stdout="", stderr="No! Do not call me!\n")
    if app == "no-version":
        return Pipe(
            returncode=0, stdout="this application does not use versioning", stderr=""
        )
    if app == "many-versions":
        return Pipe(
            returncode=0, stdout="many versions 3.14.15 (from packages 2.71)", stderr=""
        )
    if app == "python":
        return Pipe(
            returncode=0, stdout=f"Python {platform.python_version()}", stderr=""
        )
    return None


# pylint: disable-next=redefined-outer-name
def test_gather_errors(flow_cfg: env.FlowConfig, mocker):
    mocker.patch(
        "proj_flow.base.cmd.is_tool", wraps=lambda prog: not prog.endswith("0")
    )
    mocker.patch("proj_flow.base.cmd.run", wraps=_faux_run)

    rt = env.Runtime.from_flow_cfg(flow_cfg)
    steps: list[StepLike] = [
        StepLike([f"python0 ~= {platform.python_version()}"]),
        StepLike(
            [
                f"python<{platform.python_version()}",
                "python -m venv",
                f"python<!{platform.python_version()}",
            ]
        ),
        StepLike([f"python -m proj_flow != {__version__}"]),
        StepLike(
            [
                "non-tool",
                "angry",
                "no-version",
                "many-versions ~= 3",
                "no-version~=0.0.0",
            ]
        ),
    ]

    sys_exit_called = False
    with Capture() as capture:
        try:
            dependency.verify(dependency.gather(steps), rt)
        except SystemError:
            sys_exit_called = True

    assert not sys_exit_called
    assert (
        capture.stderr == ""
        "No! Do not call me!\n"
        "proj-flow: no-version: could not read version for `~=0.0.0`\n"
        "proj-flow: proj_flow: version `0.16.0` does not match `!= 0.16.0`\n"
        "proj-flow: python0: tool is missing\n"
        "proj-flow: python: version `3.10.12` does not match `<!3.10.12`\n"
        "proj-flow: python: version `3.10.12` does not match `<3.10.12`\n"
        "proj-flow: venv: Python package is missing: No package metadata was found for venv\n"
    )
    assert capture.stdout == ""
