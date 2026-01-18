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


@arg.command("webidl", "depfile")
def depfile(
    config_path: typing.Annotated[
        str, arg.Argument(help="Input configuration", names=["--cfg"], meta="json-file")
    ],
    binary_dir: typing.Annotated[
        str,
        arg.Argument(
            help="Project binary dir", names=["--binary-dir"], meta="project-binary-dir"
        ),
    ],
    output_path: typing.Annotated[
        str | None,
        arg.Argument(
            help="Output path", names=["--out"], meta="dependency-file", opt=True
        ),
    ],
    rt: env.Runtime,
):
    """Write the dependency file for CMake generators to use"""

    cmake_dirs = CMakeDirs.from_config_path(
        Path(config_path), project_binary_dir=Path(binary_dir)
    )
    global_ctx = cmake_dirs.my_defines()

    config_filename = Path(config_path).absolute()
    config = TemplateConfig.load_config(
        config_filename, global_ctx, cmake_dirs.project_source_dir
    )

    output = (
        Path(output_path)
        if output_path
        else cmake_dirs.dependency_from_config(Path(config_path))
    )

    flat_deps: dict[str, set[str]] = {}

    for rule in config.rules:
        for outname, inputs in rule.get_dependencies(None, config_filename).items():
            try:
                flat_deps[outname].update(inputs)
            except KeyError:
                flat_deps[outname] = set(inputs)
    reverse: dict[str, set[str]] = {}
    for key, value in flat_deps.items():
        val = ";".join(sorted(value))
        try:
            reverse[val].update(key)
        except KeyError:
            reverse[val] = {key}

    rules: list[dict] = []
    for deps, tgts in reverse.items():
        dependency = deps.split(";")
        target = [{"sep": " \\\n", "pathname": pathname} for pathname in tgts]
        target[0]["sep"] = ""
        rules.append({"dependency": dependency, "target": target})

    text = load_package_template("depfile")
    update_file_if_needed(
        output,
        chevron.render(text, {"rule": rules}),
        f"Generating {output.as_posix()}",
    )
