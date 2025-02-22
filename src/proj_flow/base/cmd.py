# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.base.cmd** defines environment for `proj_flow.api.env.Runtime`.
"""

import os
import shutil
import subprocess
from contextlib import contextmanager
from typing import Optional


def which(cmd: str) -> Optional[str]:
    """
    Return executable path from ``PATH`` environment variable, if it is present.

    :param cmd: name of the tool to expand
    :returns: the path to an executable which would be run if the given ``cmd``
       was called. If no ``cmd`` would be called, return ``None``.
    """
    return shutil.which(cmd)


def is_tool(name: str) -> bool:
    """
    :param name: name of the tool to check
    :returns: ``True``, if :func:`which` would return a string and `False`
       otherwise
    """
    return which(name) is not None


def run(app: str, *args: str, capture_output=False):
    """
    Run command with arguments and return a :py:class:`subprocess.CompletedProcess`
    instance. Internally, this function runs :py:func:`subprocess.run` with
    encoding set to "UTF-8" and check turned off.

    :param app: name of the command to run
    :param args: additional arguments of the command
    :param capture_output: if True, both stdout and stderr are captured
    :returns: The ``CompletedProcess`` instance if the command was successfully
       ran, or ``None``.
    """
    cmd = which(app)
    if cmd is None:
        return None
    return subprocess.run(
        [cmd, *args], shell=False, encoding="UTF-8", capture_output=capture_output
    )


@contextmanager
def cd(path: str):
    prev = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev)
