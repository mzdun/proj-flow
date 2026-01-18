# Copyright (c) 2026 Marcin Zdun
# This file is licensed under MIT license (see LICENSE for details)

from pathlib import Path


def update_file_if_needed(dst: Path, contents: str, message: str | None = None):
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
