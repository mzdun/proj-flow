# Copyright (c) 2026 Marcin Zdun
# This file is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.webidl.cli.updater** writes generated files only when their contents
actually change, so the build system does not see unneeded updates.
"""

from pathlib import Path


def update_file_if_needed(dst: Path, contents: str, message: str | None = None):
    """
    Write the file, unless it already has the same contents.

    :param dst: file to write
    :param contents: new contents of the file
    :param message: message to print, when the file is written
    :returns: ``True``, if the file was written
    """
    prev = ""
    if dst.exists():
        prev = dst.read_bytes().decode("utf-8")
    if prev == contents:
        return False

    if message:
        print("-- WebIDL:", "\n-- WebIDL: ".join(message.split("\n")))

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(contents.encode("utf-8"))

    return True
