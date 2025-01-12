# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import shutil
import subprocess
from typing import Optional


def which(cmd: str) -> Optional[str]:
    return shutil.which(cmd)


def is_tool(name: str) -> bool:
    return which(name) is not None


def run(app: str, *args: str, capture_output=False):
    cmd = which(app)
    if cmd is None:
        return None
    return subprocess.run(
        [cmd, *args], check=False, encoding="UTF-8", capture_output=capture_output
    )
