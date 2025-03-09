# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import argparse
import collections
import os
import sys
from dataclasses import dataclass
from typing import List
from unittest.mock import Mock, call

import pytest

from proj_flow.api import env

from ..capture import Capture
from ..load_flow_cfg import load_flow_cfg
from ..mocks import (
    OS_MAKEDIRS,
    OS_PATH_ABSPATH,
    OS_PATH_ISDIR,
    OS_WALK,
    Directory,
    wrap_fs,
)


@pytest.fixture
def flow_cfg(mocker):
    return load_flow_cfg(mocker, user_cfg=None, proj_cfg=None)


# pylint: disable-next=redefined-outer-name
def test_runtime_simple(flow_cfg: env.FlowConfig):
    rt = env.Runtime.from_flow_cfg(flow_cfg)

    assert not rt.dry_run
    assert not rt.silent
    assert not rt.verbose
    assert not rt.official
    assert not rt.no_coverage
    assert rt.use_color
    assert rt.only_host
    assert not rt.secrets

    args = argparse.Namespace()
    os.environ["NO_COVERAGE"] = "no-coverage"
    rt = env.Runtime.from_cli(args, flow_cfg)
    del os.environ["NO_COVERAGE"]
    assert rt.no_coverage

    os.environ["RELEASE"] = "true"
    rt = env.Runtime.from_cli(args, flow_cfg)
    del os.environ["RELEASE"]
    assert not rt.official

    os.environ["RELEASE"] = "true"
    os.environ["GITHUB_ACTIONS"] = "true"
    rt = env.Runtime.from_cli(args, flow_cfg)
    del os.environ["RELEASE"]
    del os.environ["GITHUB_ACTIONS"]
    assert rt.official

    copy = env.Runtime.clone(rt)
    assert copy.secrets == rt.secrets
    copy.secrets.append("secret-value")
    assert copy.secrets != rt.secrets


Args = collections.namedtuple("Args", ["verbose", "silent", "expected"])

PRINTING: List[Args] = [
    Args(
        verbose=False,
        silent=False,
        expected="-- Level STATUS\n-- Level ALWAYS\n-- FATAL: Level FATAL\n",
    ),
    Args(
        verbose=False,
        silent=True,
        expected="-- Level ALWAYS\n-- FATAL: Level FATAL\n",
    ),
    Args(
        verbose=True,
        silent=False,
        expected="-- Level DEBUG\n-- Level STATUS\n-- Level ALWAYS\n-- FATAL: Level FATAL\n",
    ),
    Args(
        verbose=True,
        silent=True,
        expected="-- Level DEBUG\n-- Level ALWAYS\n-- FATAL: Level FATAL\n",
    ),
]


@pytest.mark.parametrize(["verbose", "silent", "expected"], PRINTING)
# pylint: disable-next=redefined-outer-name
def test_runtime_message(flow_cfg, verbose, silent, expected):
    rt = env.Runtime(verbose=verbose, silent=silent, flow_cfg=flow_cfg)
    with Capture() as capture:
        rt.message("Level DEBUG")
        rt.message("Level STATUS", level=env.Msg.STATUS)
        rt.message("Level ALWAYS", level=env.Msg.ALWAYS)
        rt.fatal("Level FATAL")

    assert capture.stdout == ""
    assert capture.stderr == expected


# pylint: disable-next=redefined-outer-name
def test_runtime_print(flow_cfg):
    cmd = ("command", "arg", "--arg=value", "-S", "with space")

    rt = env.Runtime(silent=True, flow_cfg=flow_cfg)
    with Capture() as silent:
        rt.print(*cmd)

    assert silent.stdout == ""
    assert silent.stderr == ""

    rt = env.Runtime(silent=False, flow_cfg=flow_cfg)
    with Capture() as printing:
        rt.print(*cmd)

    assert printing.stdout == ""
    assert (
        printing.stderr
        == "\x1b[33mcommand\x1b[m arg \x1b[2;37m--arg=value\x1b[m \x1b[2;37m-S\x1b[m \x1b[2;34m'with space'\x1b[m\n"
    )

    rt = env.Runtime(silent=False, flow_cfg=flow_cfg)
    with Capture() as raw:
        rt.print(*cmd, raw=True)

    assert raw.stdout == ""
    assert (
        raw.stderr
        == "\x1b[33mcommand\x1b[m arg \x1b[2;37m--arg=value\x1b[m \x1b[2;37m-S\x1b[m with space\n"
    )


Pipe = collections.namedtuple("Pipe", ["returncode", "stdout", "stderr"])


def _faux_run(args: List[str], capture_output=False, **_kw):
    if "--fail" in args:
        return Pipe(returncode=1, stdout="", stderr="")
    stdout = f"{args[0]} called\n"
    if capture_output:
        return Pipe(returncode=0, stdout=stdout, stderr="")

    sys.stdout.write(stdout)
    return Pipe(returncode=0, stdout="", stderr="")


@dataclass
class Result:
    noticed_exit: bool = False
    stdout: str = ""
    stderr: str = ""
    captured_stdout: str = ""
    captured_stderr: str = ""
    returncode: int = 0


# pylint: disable-next=redefined-outer-name
def _cmd(flow_cfg: env.FlowConfig, *args: str, **kwargs):
    rt = env.Runtime(**kwargs, flow_cfg=flow_cfg)
    noticed_exit = False
    returncode = -1

    with Capture() as capture:
        try:
            returncode = rt.cmd(*args)
        except SystemExit:
            noticed_exit = True

    return Result(
        noticed_exit=noticed_exit,
        stdout=capture.stdout,
        stderr=capture.stderr,
        returncode=returncode,
    )


def _capture(
    # pylint: disable-next=redefined-outer-name
    flow_cfg: env.FlowConfig,
    *args: str,
    capture_silent: bool = False,
    **kwargs,
):
    rt = env.Runtime(**kwargs, flow_cfg=flow_cfg)
    noticed_exit = False
    returncode = -1
    captured_stdout = ""
    captured_stderr = ""

    with Capture() as capture:
        try:
            proc = rt.capture(*args, silent=capture_silent)
            captured_stdout = proc.stdout
            captured_stderr = proc.stderr
            returncode = proc.returncode
        except SystemExit:
            noticed_exit = True

    return Result(
        noticed_exit=noticed_exit,
        stdout=capture.stdout,
        stderr=capture.stderr,
        captured_stdout=captured_stdout,
        captured_stderr=captured_stderr,
        returncode=returncode,
    )


# pylint: disable-next=redefined-outer-name
def test_runtime_cmd(flow_cfg, mocker):
    mocker.patch("subprocess.run", wraps=_faux_run)
    assert _cmd(flow_cfg, "program", "--arg", "value") == Result(
        stdout="program called\n",
        stderr="\x1b[33mprogram\x1b[m \x1b[2;37m--arg\x1b[m value\n",
    )
    assert _cmd(flow_cfg, "program", "--arg", "value", silent=True) == Result(
        stdout="program called\n"
    )
    assert _cmd(flow_cfg, "program", "--arg", "value", dry_run=True) == Result(
        stderr="\x1b[33mprogram\x1b[m \x1b[2;37m--arg\x1b[m value\n",
    )
    assert (
        _cmd(flow_cfg, "program", "--arg", "value", silent=True, dry_run=True)
        == Result()
    )
    assert _cmd(flow_cfg, "application", "--arg", "value", "--fail") == Result(
        stderr="\x1b[33mapplication\x1b[m \x1b[2;37m--arg\x1b[m value \x1b[2;37m--fail\x1b[m\n"
        "proj-flow: error: application ended in failure, exiting\n",
        noticed_exit=True,
        returncode=-1,
    )
    assert _cmd(flow_cfg, "script", "--arg", "value", "--fail", silent=True) == Result(
        stderr="proj-flow: error: script ended in failure, exiting\n",
        noticed_exit=True,
        returncode=-1,
    )
    assert _cmd(
        flow_cfg, "application", "--arg", "value", "--fail", dry_run=True
    ) == Result(
        stderr="\x1b[33mapplication\x1b[m \x1b[2;37m--arg\x1b[m value \x1b[2;37m--fail\x1b[m\n",
    )
    assert (
        _cmd(flow_cfg, "script", "--arg", "value", "--fail", silent=True, dry_run=True)
        == Result()
    )


# pylint: disable-next=redefined-outer-name
def test_runtime_capture(flow_cfg, mocker):
    mocker.patch("subprocess.run", wraps=_faux_run)
    assert _capture(flow_cfg, "program", "--arg", "value") == Result(
        captured_stdout="program called\n",
        stderr="\x1b[33mprogram\x1b[m \x1b[2;37m--arg\x1b[m value\n",
    )
    assert _capture(flow_cfg, "program", "--arg", "value", dry_run=True) == Result(
        captured_stdout="program called\n",
        stderr="\x1b[33mprogram\x1b[m \x1b[2;37m--arg\x1b[m value\n",
    )
    assert _capture(flow_cfg, "program", "--arg", "value", silent=True) == Result(
        captured_stdout="program called\n",
    )
    assert _capture(
        flow_cfg, "program", "--arg", "value", capture_silent=True
    ) == Result(
        captured_stdout="program called\n",
    )


# pylint: disable-next=redefined-outer-name
def test_runtime_ops_dry_run(flow_cfg, mocker):
    mock_fs: Directory = {"from": {"directory": {}}}
    mocked = wrap_fs(mock_fs, mocker, OS_PATH_ISDIR, OS_PATH_ABSPATH, OS_MAKEDIRS)

    mkdirs = mocked[OS_MAKEDIRS]
    abspath = mocked[OS_PATH_ABSPATH]
    copytree: Mock = mocker.patch("shutil.copytree")
    copy: Mock = mocker.patch("shutil.copy")

    rt = env.Runtime(dry_run=True, flow_cfg=flow_cfg)
    with Capture() as console:
        rt.mkdirs("to/directory")
        rt.cp("from/directory", "to/directory")

    assert console.stdout == ""
    assert (
        console.stderr == "\x1b[33mmkdir\x1b[m \x1b[2;37m-p\x1b[m to/directory\n"
        "\x1b[33mcp\x1b[m \x1b[2;37m-r\x1b[m from/directory to/directory\n"
    )
    mkdirs.assert_not_called()
    abspath.assert_not_called()
    copytree.assert_not_called()
    copy.assert_not_called()


# pylint: disable-next=redefined-outer-name
def test_runtime_ops_no_filter(flow_cfg, mocker):
    mock_fs: Directory = {"from": {"directory": {}}}
    mocked = wrap_fs(mock_fs, mocker, OS_PATH_ISDIR, OS_PATH_ABSPATH, OS_MAKEDIRS)

    def stub(*_args, **_kwargs):
        return 0

    mkdirs = mocked[OS_MAKEDIRS]
    abspath = mocked[OS_PATH_ABSPATH]
    copytree: Mock = mocker.patch("shutil.copytree", wraps=stub)
    copy: Mock = mocker.patch("shutil.copy", wraps=stub)

    rt = env.Runtime(dry_run=False, flow_cfg=flow_cfg)
    with Capture() as console:
        rt.mkdirs("to/directory")
        rt.cp("from/directory", "to/directory")

    assert console.stdout == ""
    assert (
        console.stderr == "\x1b[33mmkdir\x1b[m \x1b[2;37m-p\x1b[m to/directory\n"
        "\x1b[33mcp\x1b[m \x1b[2;37m-r\x1b[m from/directory to/directory\n"
    )
    mkdirs.assert_called_with("to/directory", exist_ok=True)
    abspath.assert_called_once_with("to/directory")
    copytree.assert_called_once_with(
        "from/directory", "to/directory", dirs_exist_ok=True, symlinks=True
    )
    copy.assert_not_called()


# pylint: disable-next=redefined-outer-name
def test_runtime_ops_no_filter_file(flow_cfg, mocker):
    def stub(*_args, **_kwargs):
        return 0

    def file_not_found(*args, **_kwargs):
        raise FileNotFoundError(f"{args[0]} not found")

    mock_fs: Directory = {"from": {"file": True}, "to": {"directory": {}}}
    mocked = wrap_fs(mock_fs, mocker, OS_PATH_ISDIR, OS_PATH_ABSPATH, OS_MAKEDIRS)

    mkdirs = mocked[OS_MAKEDIRS]
    abspath = mocked[OS_PATH_ABSPATH]
    copytree: Mock = mocker.patch("shutil.copytree", wraps=stub)
    copy: Mock = mocker.patch("shutil.copy", wraps=stub)

    rt = env.Runtime(dry_run=False, flow_cfg=flow_cfg)
    with Capture() as console:
        rt.cp("from/file", "to/directory")

    assert console.stdout == ""
    assert console.stderr == "\x1b[33mcp\x1b[m from/file to/directory\n"
    mkdirs.assert_not_called()
    abspath.assert_called_with("to/directory")
    copytree.assert_not_called()
    copy.assert_called_once_with("from/file", "to/directory", follow_symlinks=False)

    copy2: Mock = mocker.patch("shutil.copy", wraps=file_not_found)
    with Capture() as console2:
        rt.cp("from/file", "to/directory")

    assert (
        console2.stderr == "\x1b[33mcp\x1b[m from/file to/directory\n"
        "from/file not found\n"
    )
    copy2.assert_called_once_with("from/file", "to/directory", follow_symlinks=False)


# pylint: disable-next=redefined-outer-name
def test_runtime_ops_no_filter_file_to_file(flow_cfg, mocker):
    def stub(*_args, **_kwargs):
        return 0

    mock_fs: Directory = {"from": {"file": True}, "to": {}}
    mocked = wrap_fs(mock_fs, mocker, OS_PATH_ISDIR, OS_PATH_ABSPATH, OS_MAKEDIRS)

    mkdirs = mocked[OS_MAKEDIRS]
    abspath = mocked[OS_PATH_ABSPATH]
    copytree: Mock = mocker.patch("shutil.copytree", wraps=stub)
    copy: Mock = mocker.patch("shutil.copy", wraps=stub)

    rt = env.Runtime(dry_run=False, flow_cfg=flow_cfg)
    with Capture() as console:
        rt.cp("from/file", "to/file")

    assert console.stdout == ""
    assert console.stderr == "\x1b[33mcp\x1b[m from/file to/file\n"
    mkdirs.assert_called_with("to", exist_ok=True)
    abspath.assert_called_with("to/file")
    copytree.assert_not_called()
    copy.assert_called_once_with("from/file", "to/file", follow_symlinks=False)


# pylint: disable-next=redefined-outer-name
def test_runtime_ops_filter(flow_cfg, mocker):
    def stub(*_args, **_kwargs):
        return 0

    mock_fs: Directory = {
        "packages": {
            "description.txt": True,
            "package-1.0.0-debian-x86_64.deb": True,
            "package-1.0.0-ubuntu-22.04-x86_64.tar.gz": True,
            "package-1.0.0-windows-x86_64.zip": True,
            "subdir": {
                "package-1.0.0-debian-x86_64.deb": True,
                "package-1.0.0-ubuntu-22.04-x86_64.tar.gz": True,
                "package-1.0.0-windows-x86_64.zip": True,
            },
        },
        "archive directory": {},
    }
    mocked = wrap_fs(
        mock_fs, mocker, OS_PATH_ISDIR, OS_PATH_ABSPATH, OS_MAKEDIRS, OS_WALK
    )

    mkdirs = mocked[OS_MAKEDIRS]
    abspath = mocked[OS_PATH_ABSPATH]
    walk = mocked[OS_WALK]
    copytree: Mock = mocker.patch("shutil.copytree", wraps=stub)
    copy: Mock = mocker.patch("shutil.copy", wraps=stub)

    rt = env.Runtime(dry_run=False, flow_cfg=flow_cfg)
    with Capture() as console:
        rt.cp("packages", "archive directory", r"^package-1\.0\.0-.*$")

    assert console.stdout == ""
    assert (
        console.stderr
        == "\x1b[33mcp\x1b[m \x1b[2;37m-r\x1b[m packages \x1b[2;34m'archive directory'\x1b[m\n"
    )
    mkdirs.assert_called_with("archive directory", exist_ok=True)
    walk.assert_called_once_with("packages")
    abspath.assert_has_calls(
        [
            call("packages"),
            call("packages/description.txt"),
            call("packages"),
            call("packages/package-1.0.0-debian-x86_64.deb"),
            call("packages"),
            call("packages/package-1.0.0-ubuntu-22.04-x86_64.tar.gz"),
            call("packages"),
            call("packages/package-1.0.0-windows-x86_64.zip"),
            call("archive directory/package-1.0.0-debian-x86_64.deb"),
            call("archive directory/package-1.0.0-ubuntu-22.04-x86_64.tar.gz"),
            call("archive directory/package-1.0.0-windows-x86_64.zip"),
        ]
    )
    copytree.assert_not_called()
    copy.assert_has_calls(
        [
            call(
                "packages/package-1.0.0-debian-x86_64.deb",
                "archive directory/package-1.0.0-debian-x86_64.deb",
                follow_symlinks=False,
            ),
            call(
                "packages/package-1.0.0-ubuntu-22.04-x86_64.tar.gz",
                "archive directory/package-1.0.0-ubuntu-22.04-x86_64.tar.gz",
                follow_symlinks=False,
            ),
            call(
                "packages/package-1.0.0-windows-x86_64.zip",
                "archive directory/package-1.0.0-windows-x86_64.zip",
                follow_symlinks=False,
            ),
        ]
    )


# pylint: disable-next=redefined-outer-name
def test_runtime_ops_filter_not_found(flow_cfg, mocker):
    def stub(*args, **_kwargs):
        raise FileNotFoundError(f"{args[0]} not found")

    mock_fs: Directory = {
        "packages": {
            "description.txt": True,
            "package-1.0.0-debian-x86_64.deb": True,
            "package-1.0.0-ubuntu-22.04-x86_64.tar.gz": True,
            "package-1.0.0-windows-x86_64.zip": True,
            "subdir": {
                "package-1.0.0-debian-x86_64.deb": True,
                "package-1.0.0-ubuntu-22.04-x86_64.tar.gz": True,
                "package-1.0.0-windows-x86_64.zip": True,
            },
        },
        "archive directory": {},
    }
    mocked = wrap_fs(
        mock_fs, mocker, OS_PATH_ISDIR, OS_PATH_ABSPATH, OS_MAKEDIRS, OS_WALK
    )

    mkdirs = mocked[OS_MAKEDIRS]
    abspath = mocked[OS_PATH_ABSPATH]
    walk = mocked[OS_WALK]
    copytree: Mock = mocker.patch("shutil.copytree", wraps=stub)
    copy: Mock = mocker.patch("shutil.copy", wraps=stub)

    rt = env.Runtime(dry_run=False, flow_cfg=flow_cfg)
    with Capture() as console:
        rt.cp("packages", "archive directory", r"^package-1\.0\.0-.*$")

    assert console.stdout == ""
    assert (
        console.stderr
        == "\x1b[33mcp\x1b[m \x1b[2;37m-r\x1b[m packages \x1b[2;34m'archive directory'\x1b[m\n"
        "packages/package-1.0.0-debian-x86_64.deb not found\n"
    )
    mkdirs.assert_called_with("archive directory", exist_ok=True)
    walk.assert_called_once_with("packages")
    abspath.assert_has_calls(
        [
            call("packages"),
            call("packages/description.txt"),
            call("packages"),
            call("packages/package-1.0.0-debian-x86_64.deb"),
            call("packages"),
            call("packages/package-1.0.0-ubuntu-22.04-x86_64.tar.gz"),
            call("packages"),
            call("packages/package-1.0.0-windows-x86_64.zip"),
            call("archive directory/package-1.0.0-debian-x86_64.deb"),
        ]
    )
    copytree.assert_not_called()
    copy.assert_has_calls(
        [
            call(
                "packages/package-1.0.0-debian-x86_64.deb",
                "archive directory/package-1.0.0-debian-x86_64.deb",
                follow_symlinks=False,
            ),
        ]
    )
