# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)


import copy
import json
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
from typing import Any, Callable, cast

import chevron

from proj_flow.ext.webidl.model.builders import ExtAttrsContextBuilders, TypeReplacement

package_root = Path(__file__).parent.parent
templates_dir = package_root / "data" / "templates"


def load_package_template(name: str):
    path = templates_dir / f"{name}.mustache"
    return path.read_text(encoding="UTF-8")


@dataclass
class CMakeDirs:
    base_dir: Path
    project_source_dir: Path
    project_binary_dir: Path
    current_source_dir: Path
    current_binary_dir: Path

    @staticmethod
    def from_config_path(config: Path, project_binary_dir: Path):
        config = config.absolute()
        project_binary_dir = project_binary_dir.absolute()
        base_dir = config.parent
        project_source_dir = Path().absolute()
        current_source_dir = project_source_dir

        for parent in config.parents:
            cmake_lists = parent / "CMakeLists.txt"
            if cmake_lists.exists():
                current_source_dir = parent
                break

        current_binary_dir = project_binary_dir / current_source_dir.relative_to(
            project_source_dir
        )

        return CMakeDirs(
            base_dir=base_dir,
            project_source_dir=project_source_dir,
            project_binary_dir=project_binary_dir,
            current_source_dir=current_source_dir,
            current_binary_dir=current_binary_dir,
        )

    def filename_from_config(self, config: Path, ext: str):
        in_source = config.absolute().relative_to(self.current_source_dir)
        in_build = self.current_binary_dir / in_source
        return Path(in_build.as_posix() + ext)

    def dependency_from_config(self, config: Path):
        return self.filename_from_config(config, ".deps")

    def cmake_from_config(self, config: Path):
        return self.filename_from_config(config, ".cmake")

    def my_defines(self):
        return {
            "PROJECT_SOURCE_DIR": self.project_source_dir.as_posix(),
            "PROJECT_BINARY_DIR": self.project_binary_dir.as_posix(),
            "CMAKE_CURRENT_SOURCE_DIR": self.current_source_dir.as_posix(),
            "CMAKE_CURRENT_BINARY_DIR": self.current_binary_dir.as_posix(),
        }

    def expand_prefix(self, filename: str):
        if "${" not in filename:
            return Path(filename)
        defs = self.my_defines()
        chunks = filename.split("${")
        result = chunks[0]
        chunks = chunks[1:]
        for chunk in chunks:
            var, rest = chunk.split("}", 1)
            result += defs.get(var, f"${{{var}}}") + rest
        return Path(result)

    def prefix(self, filename: str):
        if "${" in filename:
            return Path(filename)

        full = self.base_dir / filename

        if full.is_relative_to(self.current_binary_dir):
            return Path("${CMAKE_CURRENT_BINARY_DIR}") / full.relative_to(
                self.current_binary_dir
            )
        if full.is_relative_to(self.project_binary_dir):
            return Path("${PROJECT_BINARY_DIR}") / full.relative_to(
                self.project_binary_dir
            )
        if full.is_relative_to(self.current_source_dir):
            return Path("${CMAKE_CURRENT_SOURCE_DIR}") / full.relative_to(
                self.current_source_dir
            )
        if full.is_relative_to(self.project_source_dir):
            return Path("${PROJECT_SOURCE_DIR}") / full.relative_to(
                self.project_source_dir
            )

        return Path(filename)

    def make_abs_path(self):
        def impl(filename: str):
            return self.prefix(filename)

        return impl


def _relative(path: Path, basedir: Path | None):
    if not basedir:
        return path
    return path.relative_to(basedir, walk_up=True)


class Rebuild:
    @staticmethod
    def __rebuild_map(data: dict, global_ctx: dict[str, str]):
        for key, value in data.items():
            data[key] = Rebuild.__rebuild_any(value, global_ctx)
        return data

    @staticmethod
    def __rebuild_list(data: list, global_ctx: dict[str, str]):
        for index, value in enumerate(data):
            data[index] = Rebuild.__rebuild_any(value, global_ctx)
        return data

    @staticmethod
    def __rebuild_str(data: str, global_ctx: dict[str, str]):
        return chevron.render(data, global_ctx)

    @staticmethod
    def __rebuild_any(data, global_ctx: dict[str, str]):
        if isinstance(data, str):
            return Rebuild.__rebuild_str(data, global_ctx)
        if isinstance(data, list):
            return Rebuild.__rebuild_list(data, global_ctx)
        if isinstance(data, dict):
            return Rebuild.__rebuild_map(data, global_ctx)

        return data

    @staticmethod
    def rebuild(initial_context: dict, global_ctx: dict[str, str]):
        return Rebuild.__rebuild_map(initial_context, global_ctx)

    @staticmethod
    def rebuild_any(initial_context, global_ctx: dict[str, str]):
        return Rebuild.__rebuild_any(initial_context, global_ctx)


@dataclass
class ConfigOutput:
    output_name: str
    mustache_template: str | None
    output_template: str | None
    lang: str | None
    types: str | None
    partials: str | None
    initial_context: dict
    initial_versioned_context: dict
    debug: bool
    ndebug: bool

    @staticmethod
    def from_config(
        data: dict[str, str | dict[str, Any]],
        root_default: "ConfigOutput",
        allow_versioned: bool,
    ):
        result = [
            ConfigOutput.from_dict(key, item, allow_versioned)
            for key, item in data.items()
        ]

        for index in range(len(result)):
            default = result[index]
            if default.output_name != "":
                continue

            del result[index]
            for item in result:
                item.update_from(default, allow_versioned)

            break

        for item in result:
            item.update_from(root_default, allow_versioned)

        return result

    @staticmethod
    def from_dict(
        output_name: str, data: str | dict[str, str | dict], allow_versioned: bool
    ) -> "ConfigOutput":
        if isinstance(data, str):
            return ConfigOutput(
                output_name=output_name,
                mustache_template=data,
                output_template=None,
                lang=None,
                types=None,
                partials=None,
                initial_context={},
                initial_versioned_context={},
                debug=False,
                ndebug=False,
            )

        mustache_template = cast(str | None, data.get("template", None))
        output_template = cast(str | None, data.get("path", None))
        lang = cast(str | None, data.get("lang", None))
        types = cast(str | None, data.get("types", None))
        partials = cast(str | None, data.get("partials", None))
        initial_context = copy.deepcopy(cast(dict, data.get("context", {})))
        initial_versioned_context = (
            copy.deepcopy(cast(dict, data.get("version_context", {})))
            if allow_versioned
            else {}
        )
        debug = not not data.get("debug", {})
        ndebug = not not data.get("ndebug", {})

        return ConfigOutput(
            output_name=output_name,
            mustache_template=mustache_template,
            output_template=output_template,
            lang=lang,
            types=types,
            partials=partials,
            initial_context=initial_context,
            initial_versioned_context=initial_versioned_context,
            debug=debug,
            ndebug=ndebug,
        )

    def update_from(self, default: "ConfigOutput", allow_versioned: bool):
        self.mustache_template = self.mustache_template or default.mustache_template
        self.output_template = self.output_template or default.output_template
        self.lang = self.lang or default.lang
        self.types = self.types or default.types
        self.partials = self.partials or default.partials
        self.initial_context = {
            **copy.deepcopy(default.initial_context),
            **copy.deepcopy(self.initial_context),
        }
        if allow_versioned:
            self.initial_versioned_context = {
                **copy.deepcopy(default.initial_versioned_context),
                **copy.deepcopy(self.initial_versioned_context),
            }
        self.debug = self.debug or default.debug
        self.ndebug = self.ndebug or default.ndebug


def _file_props(path: Path):
    suffixes = "".join(path.suffixes)
    name = path.name
    shortest = name[: -len(suffixes)]
    return {
        "filename": path.as_posix(),
        "dirname": path.parent.as_posix(),
        "basename": path.name,
        "stem": path.stem,
        "suffix": path.suffix,
        "suffixes": suffixes,
        "shortest_stem": shortest,
    }


def _rel_file_props(path: Path, root: Path, version: int):
    props: dict = _file_props(path)
    if path.is_relative_to(root):
        rel = path.relative_to(root)
        props["relative"] = {
            "filename": rel.as_posix(),
            "dirname": rel.parent.as_posix(),
        }
    props["version"] = version
    return props


@dataclass
class OutputTemplate:
    config: ConfigOutput
    context: dict
    abs_path: Callable[[str], Path]

    def freeze(self, version: int, versions: list[int] | None = None):
        context = copy.deepcopy(self.context)
        context["version"] = version
        expand_path = lambda text: chevron.render(template=text, data=context)

        output_name = expand_path(str(self.config.output_name))
        context["PATH"] = str(output_name)

        if self.config.output_template:
            output_name = expand_path(self.config.output_template)
        output_name = self.abs_path(output_name)

        mustache_template = None
        if self.config.mustache_template:
            mustache_template = self.abs_path(
                expand_path(self.config.mustache_template)
            )

        types = None
        if self.config.types:
            types = self.abs_path(expand_path(self.config.types))

        partials = None
        if self.config.partials:
            partials = self.abs_path(expand_path(self.config.partials))

        initial_context = Rebuild.rebuild(self.config.initial_context, context)
        if versions:
            for key, value in self.config.initial_versioned_context.items():
                initial_context[key] = [
                    Rebuild.rebuild_any(value, {**context, "version": str(ver)})
                    for ver in versions
                ]

        return Output(
            output=output_name,
            mustache_template=mustache_template,
            lang=self.config.lang,
            types=types,
            partials=partials,
            initial_context=initial_context,
            debug=self.config.debug and not self.config.ndebug,
            name_context=context,
        )

    @staticmethod
    def from_config(
        context: dict[str, str],
        root_default: ConfigOutput,
        data: dict[str, str | dict[str, Any]],
        abs_path: Callable[[str], Path],
        allow_versioned: bool,
    ):
        return [
            OutputTemplate(config=config, context=context, abs_path=abs_path)
            for config in ConfigOutput.from_config(data, root_default, allow_versioned)
        ]


@dataclass
class Output:
    output: Path
    mustache_template: Path | None
    lang: str | None
    types: Path | None
    partials: Path | None
    initial_context: dict
    debug: bool
    name_context: dict

    @staticmethod
    def filename_context(filename: str | Path, root_dir: Path, version: int):
        return _rel_file_props(Path(filename), root_dir, version=version)

    @staticmethod
    def abs_path(basedir: Path, path: str):
        return basedir / path

    def get_type_replacements(self):
        return TypeReplacement.load_config(self.lang, self.types)


@dataclass
class TemplateRule:
    inputs: list[Path]
    outputs: list[OutputTemplate]
    versioned_outputs: list[OutputTemplate]

    @staticmethod
    def from_config(
        global_ctx: dict, source_dir: Path, data: dict, abs_path: Callable[[str], Path]
    ):
        templates = cast(dict[str, dict[str, str | dict]], data.get("templates", {}))
        inputs = cast(list[dict[str, str]], data.get("inputs", []))
        return cast(
            list[TemplateRule],
            list(
                filter(
                    lambda v: v is not None,
                    [
                        TemplateRule.__get_rule(
                            cast(list[str] | str, input.get("idl", [])),
                            cast(str | None, input.get("template")),
                            cast(str | None, input.get("versioned_template")),
                            global_ctx,
                            source_dir,
                            templates,
                            abs_path,
                        )
                        for input in inputs
                    ],
                )
            ),
        )

    @staticmethod
    def __get_rule(
        input_names: str | list[str],
        suite_id: str | None,
        versioned_suite_id: str | None,
        global_ctx: dict,
        source_dir: Path,
        templates: dict[str, dict[str, str | dict[str, Any]]],
        abs_path: Callable[[str], Path],
    ):
        if suite_id is None:
            return None

        names = [input_names] if isinstance(input_names, str) else input_names
        context = {
            **global_ctx,
            "input": Output.filename_context(names[0], source_dir, version=1),
        }

        inputs = [abs_path(name) for name in names]
        root_config = ConfigOutput.from_dict(
            "", templates.get("", {}).get("", {}), allow_versioned=True
        )
        outputs = OutputTemplate.from_config(
            context,
            root_config,
            templates.get(suite_id, {}),
            abs_path,
            allow_versioned=False,
        )
        versioned_outputs = OutputTemplate.from_config(
            context,
            root_config,
            templates.get(versioned_suite_id, {}) if versioned_suite_id else {},
            abs_path,
            allow_versioned=True,
        )

        return TemplateRule(
            inputs=inputs, outputs=outputs, versioned_outputs=versioned_outputs
        )

    def get_dependencies(
        self,
        max_version: int,
        CMAKE_CURRENT_BINARY_DIR: Path | None,
        *additional_inputs: Path,
    ) -> dict[str, list[str]]:
        def rel(path: Path):
            return _relative(path, CMAKE_CURRENT_BINARY_DIR)

        result: dict[str, list[str]] = {}
        versions = list(range(1, max_version + 1))
        for output in self.outputs:
            for version in versions:
                current_inputs: list[Path] = [*self.inputs, *additional_inputs]
                out = output.freeze(version)
                if out.mustache_template:
                    current_inputs.append(out.mustache_template)
                result[rel(out.output).as_posix()] = [
                    path.as_posix() for path in current_inputs
                ]
        for output in self.versioned_outputs:
            current_inputs: list[Path] = [*self.inputs, *additional_inputs]
            out = output.freeze(1, versions=versions)
            if out.mustache_template:
                current_inputs.append(out.mustache_template)
            result[rel(out.output).as_posix()] = [
                path.as_posix() for path in current_inputs
            ]
        return result


@dataclass
class TemplateConfig:
    version: int
    rules: list[TemplateRule]
    ext_attrs: ExtAttrsContextBuilders

    @staticmethod
    def load_config(
        config: Path,
        context: dict,
        source_dir: Path,
        abs_path: Callable[[str], Path] | None = None,
    ):
        with config.open(encoding="UTF-8") as json_file:
            data = cast(dict, json.load(json_file))

        config_dep = config.absolute()
        basedir = config_dep.parent

        return TemplateConfig(
            version=cast(int, data.get("version", 1)),
            rules=TemplateRule.from_config(
                context, source_dir, data, abs_path or (lambda path: basedir / path)
            ),
            ext_attrs=ExtAttrsContextBuilders.builtin().merge(
                ExtAttrsContextBuilders.from_config(data)
            ),
        )
