# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import typing
from pathlib import Path

from proj_flow.api import arg, env
from proj_flow.ext.webidl.cli.updater import update_file_if_needed


@arg.command("webidl", "init")
def init(rt: env.Runtime):
    """Copy the main WebIDL CMake config to .flow/cmake"""

    out_dir_name = Path(".flow") / "cmake"
    in_dir_name = Path(__file__).parent.parent / "data" / "init"

    for root, _dirs, files in in_dir_name.walk():
        for filename in files:
            in_path = root / filename
            out_path = out_dir_name / in_path.relative_to(in_dir_name)
            update_file_if_needed(
                out_path,
                in_path.read_bytes().decode("utf-8"),
                f"adding {out_path.as_posix()}",
            )
