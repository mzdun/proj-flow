# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import json
import sys
import typing
from dataclasses import asdict
from pathlib import Path
from pprint import pprint

import chevron

from proj_flow.api import arg, env
from proj_flow.ext.webidl.base.config import (
    CMakeDirs,
    Output,
    TemplateConfig,
    templates_dir,
)
from proj_flow.ext.webidl.cli.updater import update_file_if_needed
from proj_flow.ext.webidl.model.ast import Definitions
from proj_flow.ext.webidl.registry import webidl_visitors


def aslist(items: list):
    return [asdict(item) for item in items]


T = typing.TypeVar("T")
P = typing.TypeVar("P")


def conv(conv: typing.Callable[[T], P], maybe: T | None) -> P | None:
    if maybe is None:
        return None
    return conv(maybe)


@arg.command("webidl", "gen")
def gen(
    config_path: typing.Annotated[
        str, arg.Argument(help="Input configuration", names=["--cfg"], meta="json-file")
    ],
    binary_dir: typing.Annotated[
        str,
        arg.Argument(
            help="Project binary dir", names=["--binary-dir"], meta="project-binary-dir"
        ),
    ],
    rt: env.Runtime,
):
    """Run mustache codegen on WebIDL definitions"""

    config_filename = Path(config_path)
    cmake_dirs = CMakeDirs.from_config_path(
        config_filename, project_binary_dir=Path(binary_dir)
    )

    global_ctx = cmake_dirs.my_defines()
    config_filename = Path(config_path).absolute()
    config = TemplateConfig.load_config(
        config_filename, global_ctx, cmake_dirs.project_source_dir
    )

    global_ctx["version"] = str(config.version)

    pkg_partials: dict[str, str] = {}
    partials_dir = templates_dir / "partials"
    ext = ".mustache"
    for root, _dirs, files in partials_dir.walk():
        for path in [
            root / filename for filename in files if filename[-len(ext) :] == ext
        ]:
            path_id = path.relative_to(partials_dir).with_name(path.stem)
            lang_id = str(path_id.parents[0])
            partial = path_id.as_posix()[len(lang_id) + 1 :]
            partial = f"pkg-{lang_id}:{partial}"
            pkg_partials[partial] = path.read_text(encoding="UTF-8")

            if rt.verbose:
                print(f"-- WebIDL: adding `{partial}' package partial")

    for rule in config.rules:
        names = list(map(lambda path: path.as_posix(), rule.inputs))
        context = {
            **global_ctx,
            "input": Output.filename_context(names[0], cmake_dirs.project_source_dir),
        }

        try:
            idl = Definitions.parse_and_merge(names, config.ext_attrs)
        except FileNotFoundError as e:
            p = Path(e.filename)
            print(f"{e.strerror}: {p.as_posix()}")
            sys.exit(1)
        if isinstance(idl, list):
            for error in idl:
                print(f"{error.path}:{error.error}")
            sys.exit(1)

        for visitor in webidl_visitors.get():
            visitor.on_definitions(idl)

        for output in rule.outputs:
            if not output.mustache_template:
                continue
            write_message: str | None = None
            if not rt.silent:
                fname = (
                    output.output.relative_to(cmake_dirs.project_source_dir).as_posix()
                    if output.output.is_relative_to(cmake_dirs.project_source_dir)
                    else output.output.as_posix()
                )
                write_message = f"writing {fname}"

            types = output.get_type_replacements()
            interfaces, modules_or_includes = idl.order(types)
            output_context = {
                **output.initial_context,
                **context,
                "modules_or_includes": list(sorted(modules_or_includes)),
                "interfaces": aslist(interfaces),
                "enums": aslist(idl.enum),
                "has_modules_or_includes": not not modules_or_includes,
                "has_interfaces": not not interfaces,
                "has_enums": not not idl.enum,
                "output": Output.filename_context(
                    str(output.output), cmake_dirs.project_binary_dir
                ),
            }

            kwargs = {}
            if output.partials:
                kwargs["partials_path"] = output.partials.as_posix()
            text = output.mustache_template.read_text(encoding="UTF-8")
            try:
                text = chevron.render(
                    text, output_context, partials_dict=pkg_partials, **kwargs
                )
            except chevron.ChevronError as e:
                filename = e.filename or output.mustache_template.as_posix()
                line = conv(lambda num: f":{num}", e.lineno) or ""
                col = (conv(lambda num: f":{num}", e.offset) or "") if e.lineno else ""
                print(f"{filename}{line}{col}: {e.msg}")
                if e.text:
                    print(e.text)
                    if e.offset:
                        spaces = "".join(
                            ["\t" if c == "\t" else " " for c in e.text[: e.offset]]
                        )
                        print(f"{spaces}^")
                sys.exit(1)

            update_file_if_needed(output.output, text, write_message)

            dst = output.output.with_name(output.output.name + ".json")
            update_file_if_needed(dst, json.dumps(output_context, indent=2))
