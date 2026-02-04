# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
import stat
import subprocess
import sys
from typing import Callable

from proj_flow.ext.test_runner.driver import test
from proj_flow.ext.test_runner.utils.archives import locate_unpack

_file_cache = {}
_rw_mask = stat.S_IWRITE | stat.S_IWGRP | stat.S_IWOTH
_ro_mask = 0o777 ^ _rw_mask


def _touch(test: test.Test, args: list[str]):
    filename = test.path(args[0])
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "wb") as f:
        if len(args) > 1:
            f.write(args[1].encode("UTF-8"))


def _make_RO(test: test.Test, args: list[str]):
    filename = test.path(args[0])
    mode = os.stat(filename).st_mode
    _file_cache[filename] = mode
    os.chmod(filename, mode & _ro_mask)


def _make_RW(test: test.Test, args: list[str]):
    filename = test.path(args[0])
    try:
        mode = _file_cache[filename]
    except KeyError:
        mode = os.stat(filename).st_mode | _rw_mask
    os.chmod(filename, mode)


def _unpack(test: test.Test, args: list[str]):
    archive = args[0]
    dst = args[1]
    unpack = locate_unpack(archive)[0]
    unpack(archive, test.path(dst))


def _cat(test: test.Test, args: list[str]):
    filename = args[0]
    with open(test.path(filename)) as f:
        sys.stdout.write(f.read())


def _shell(test: test.Test, args: list[str]):
    print("shell!!!")
    print("target:", test.current_env.target if test.current_env is not None else "?")
    subprocess.call("pwsh" if os.name == "nt" else "bash", shell=True, cwd=test.cwd)


HANDLERS: dict[str, tuple[int, Callable[["test.Test", list[str]], None]]] = {
    "mkdirs": (1, lambda test, args: test.makedirs(args[0])),
    "cd": (1, lambda test, args: test.chdir(args[0])),
    "rm": (1, lambda test, args: test.rmtree(args[0])),
    "touch": (1, _touch),
    "unpack": (2, _unpack),
    "store": (2, lambda test, args: test.store_output(args[0], args[1:])),
    "ro": (1, _make_RO),
    "cp": (2, lambda test, args: test.cp(args[0], args[1])),
    "rw": (1, _make_RW),
    "ls": (1, lambda test, args: test.ls(args[0])),
    "cat": (1, _cat),
    "shell": (0, _shell),
}
