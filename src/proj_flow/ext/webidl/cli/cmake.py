# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import typing
from pathlib import Path

import chevron

from proj_flow.api import arg, env
from proj_flow.ext.webidl.base.config import (
    CMakeDirs,
    TemplateConfig,
    load_package_template,
)
from proj_flow.ext.webidl.cli.updater import update_file_if_needed


@arg.command("webidl", "cmake")
def cmake(
    config_path: typing.Annotated[
        str, arg.Argument(help="Input configuration", names=["--cfg"], meta="json-file")
    ],
    binary_dir: typing.Annotated[
        str,
        arg.Argument(
            help="Project binary dir", names=["--binary-dir"], meta="project-binary-dir"
        ),
    ],
    target: typing.Annotated[
        str | None,
        arg.Argument(
            help="Name of the target to add output files to", meta="name", opt=True
        ),
    ],
    rt: env.Runtime,
):
    """Write the CMake configuration based on given config"""

    global_ctx = {
        key: f"${{{key}}}"
        for key in [
            "CMAKE_CURRENT_SOURCE_DIR",
            "CMAKE_CURRENT_BINARY_DIR",
            "PROJECT_SOURCE_DIR",
            "PROJECT_BINARY_DIR",
        ]
    }
    config_filename = Path(config_path)
    cmake_dirs = CMakeDirs.from_config_path(
        config_filename, project_binary_dir=Path(binary_dir)
    )

    abs_path = cmake_dirs.make_abs_path()

    depfile_ref = cmake_dirs.prefix(
        str(cmake_dirs.dependency_from_config(config_filename))
    )
    cmake_filename = cmake_dirs.cmake_from_config(config_filename)
    config_noext = cmake_dirs.filename_from_config(config_filename, "")

    config = TemplateConfig.load_config(
        config_filename.absolute(), global_ctx, cmake_dirs.project_source_dir, abs_path
    )

    context = {
        "config": {
            "binary": cmake_dirs.prefix(str(config_noext)).as_posix(),
            "source": cmake_dirs.prefix(str(config_filename.absolute())).as_posix(),
            "basename": config_filename.name,
        },
        "output": [
            out.output.as_posix() for rule in config.rules for out in rule.outputs
        ],
        "target": target,
        "depfile": depfile_ref.as_posix(),
    }

    text = load_package_template("cmake")
    text = chevron.render(text, data=context, partials_path=None)
    update_file_if_needed(
        cmake_filename, text, f"Generating {cmake_filename.as_posix()}"
    )
