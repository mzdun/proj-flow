# Copyright (c) 2026 Marcin Zdun
# This file is licensed under MIT license (see LICENSE for details)

from pathlib import Path

from proj_flow.api import arg


def _pragma_present(path: Path):
    with path.open(encoding="UTF-8") as text:
        for line in text:
            line = line.rstrip()
            if line == "#pragma once":
                return True
    return False


@arg.command("tools", "pragma-once")
def pragma_once():
    """Check presence and absence of ``#pragma once``, as expected"""

    code_exts = [".c", ".c++", ".cc", ".cpp", ".cxx"]
    header_exts = [".h", ".h++", ".hh", ".hpp", ".hxx"]

    paths: dict[bool, list[Path]] = {True: [], False: []}

    for root, dirs, files in Path(".").walk():
        dirs[:] = [dir_name for dir_name in dirs if dir_name not in [".git", "build"]]
        for filename in files:
            path = root / filename
            ext = path.suffix
            if ext in code_exts:
                paths[False].append(path)
            elif ext in header_exts:
                paths[True].append(path)

    for expected in paths:
        for path in paths[expected]:
            if _pragma_present(path) != expected:
                print(path.as_posix())
