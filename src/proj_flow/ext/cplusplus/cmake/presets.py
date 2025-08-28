# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.cplusplus.cmake.presets** check build directories for CMake step.
"""

import json
import os
import platform
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import cast


class MacroType(Enum):
    PRESET_NAME = 1
    GENERATOR = 2
    FILE_DIR = 3


CMAKE_SOURCE_DIR = Path(".").resolve()
CMAKE_HOST_SYSTEM_NAME = platform.uname().system

MACROS: dict[str, Path | str | MacroType] = {
    "${sourceDir}": CMAKE_SOURCE_DIR,
    "${sourceParentDir}": CMAKE_SOURCE_DIR.parent,
    "${sourceDirName}": CMAKE_SOURCE_DIR.name,
    "${presetName}": MacroType.PRESET_NAME,
    "${generator}": MacroType.GENERATOR,
    "${hostSystemName}": CMAKE_HOST_SYSTEM_NAME,
    "${fileDir}": MacroType.FILE_DIR,
    "${dollar}": "$",
    "${pathListSep}": os.pathsep,
}


@dataclass
class Preset:
    name: str
    binary_dir: str | None
    generator: str | None
    inherits: list[str]
    file_dir: Path

    def expand(self):
        if not self.binary_dir:
            return None
        chunks = self.binary_dir.split("${")
        parts: list[str | Path | MacroType] = [chunks[0]]
        for chunk in chunks[1:]:
            var_suffix = chunk.split("}", 1)
            if len(var_suffix) != 2:
                return None
            key = f"${{{var_suffix[0]}}}"
            value = MACROS.get(key, "")
            if isinstance(value, MacroType):
                if value == MacroType.PRESET_NAME:
                    value = self.name
                elif value == MacroType.GENERATOR:
                    value = self.generator or ""
                elif value == MacroType.FILE_DIR:
                    value = self.file_dir
            elif isinstance(value, Path):
                if value.is_absolute():
                    parts = []
                value = str(value)
            parts.append(value)
            parts.append(var_suffix[1])

        return Path("".join(str(part) for part in parts))


class Presets:
    def __init__(self):
        self.seen = cast(set[Path], set())
        self.result = cast(dict[str, Preset], {})

    def visit_file(self, filename: Path):
        dirname = self.__parent_from_file(filename)
        if dirname is None:
            return self.result

        includes, presets = Presets.__load_file(filename)
        self.__visit_includes(dirname, includes)
        for preset in presets:
            self.__visit_preset(dirname, preset)
        for preset in self.result.values():
            self.__merge_preset(preset)

        return self.result

    def __parent_from_file(self, filename: Path):
        key = filename.resolve()
        if key in self.seen:
            return None
        self.seen.add(key)
        return key.parent

    def __visit_includes(self, dirname: Path, includes: list[str]):
        for include in includes:
            self.visit_file(dirname / include)

    def __visit_preset(self, dirname: Path, preset: dict):
        name = cast(str | None, preset.get("name"))
        if name is None:
            return
        binary_dir = cast(str | None, preset.get("binaryDir"))
        generator = cast(str | None, preset.get("generator"))
        inherits = cast(list[str], preset.get("inherits", []))
        self.result[name] = Preset(
            name=name,
            binary_dir=binary_dir,
            generator=generator,
            inherits=inherits,
            file_dir=dirname,
        )

    def __merge_preset(self, preset: Preset):
        inherits: list[str] = []
        inherits.extend(preset.inherits)
        while inherits:
            parent = inherits[0]
            inherits = inherits[1:]
            if parent not in self.result:
                continue
            parent_preset = self.result[parent]
            inherits.extend(parent_preset.inherits)

            if parent_preset.binary_dir and not preset.binary_dir:
                preset.binary_dir = parent_preset.binary_dir
            if parent_preset.generator and not preset.generator:
                preset.generator = parent_preset.generator

    @staticmethod
    def __load_file(filename: Path):
        with open(filename, encoding="UTF-8") as f:
            data = json.load(f)
        includes = cast(list[str], data.get("include", []))
        presets = cast(list[dict], data.get("configurePresets", []))

        return (includes, presets)


def get_binary_dirs():
    presets = Presets().visit_file(Path("CMakePresets.json"))

    cwd = str(Path.cwd().as_posix()) + "/"
    result: dict[str, str] = {}
    for preset in presets.values():
        dirname = preset.expand()
        if dirname is None:
            continue
        rel = str(dirname.as_posix())
        if rel[: len(cwd)] == cwd:
            rel = rel[len(cwd) :]
        result[preset.name] = rel

    return result
