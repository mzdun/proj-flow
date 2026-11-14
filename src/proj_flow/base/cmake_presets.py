# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.base.cmake_presets** reads ``CMakePresets.json``, together
with its includes, to find the build directories of the presets for the CMake
step.
"""

import json
import os
import platform
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, TypeVar, cast


class MacroType(Enum):
    """
    Macros of ``binaryDir``, whose values depend on the preset.
    """

    #: ``${presetName}``
    PRESET_NAME = 1
    #: ``${generator}``
    GENERATOR = 2
    #: ``${fileDir}``
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
    """
    Configure preset, with the values used by *Project Flow*. After
    :meth:`Presets.visit_file`, missing values are taken from the inherited
    presets.
    """

    #: Name of the preset.
    name: str
    #: The ``binaryDir``, with the macros not expanded yet.
    binary_dir: str | None
    #: The ``CMAKE_BUILD_TYPE`` cache variable.
    build_type: str | None
    #: The ``generator``.
    generator: str | None
    #: Names of the presets this one inherits from.
    inherits: list[str]
    #: Directory of the file defining the preset.
    file_dir: Path

    def expand(self):
        """
        Expand the macros of :attr:`binary_dir`. Unknown macros expand to an
        empty string; a macro expanding to an absolute path drops everything
        before it.

        :returns: the binary directory, or ``None``, if the preset has none or
            its ``binaryDir`` has an unclosed macro
        """
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
    """
    Reader of ``CMakePresets.json`` files. Each file is read only once, so
    includes can form a graph.
    """

    def __init__(self):
        self.seen = cast(set[Path], set())
        self.result = cast(dict[str, Preset], {})

    def visit_file(self, filename: Path):
        """
        Read the configure presets of the file and of all the files it
        includes, then fill missing values of each preset from the presets it
        inherits from.

        :param filename: path of a presets file
        :returns: all the presets read so far, by name, or ``None``, if a file
            is missing
        """
        dirname = self.__parent_from_file(filename)
        if dirname is None:
            return self.result

        try:
            includes, presets = Presets.__load_file(filename)
            self.__visit_includes(dirname, includes)
            for preset in presets:
                self.__visit_preset(dirname, preset)
            for preset in self.result.values():
                self.__merge_preset(preset)
        except FileNotFoundError:
            return None

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
        cache = cast(dict, preset.get("cacheVariables", {}))
        build_type = cast(str | None, cache.get("CMAKE_BUILD_TYPE"))
        self.result[name] = Preset(
            name=name,
            binary_dir=binary_dir,
            build_type=build_type,
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
            if parent_preset.build_type and not preset.build_type:
                preset.build_type = parent_preset.build_type

    @staticmethod
    def __load_file(filename: Path):
        with open(filename, encoding="UTF-8") as f:
            data = json.load(f)
        includes = cast(list[str], data.get("include", []))
        presets = cast(list[dict], data.get("configurePresets", []))

        return (includes, presets)


def binary_dir_from_preset(preset: Preset, cwd: Path):
    """
    Mapper for :func:`visit_presets`, returning the binary directory of the
    preset.

    :param preset: the preset
    :param cwd: directory to make the path relative to, if possible
    :returns: the binary directory, or ``None``, if the preset has none
    """
    path = preset.expand()
    if not path:
        return None
    if path.is_relative_to(cwd):
        path = path.relative_to(cwd)
    return path


def get_binary_dirs():
    """
    :returns: binary directories of all the presets in ``CMakePresets.json``
        of the current directory, by preset name, or ``None``, if there is no
        such file
    """
    return visit_presets(binary_dir_from_preset)


T = TypeVar("T")


def visit_presets(mapper: Callable[[Preset, Path], T | None]):
    """
    Map all the presets of ``CMakePresets.json`` in the current directory.

    :param mapper: called with each preset and the current directory; presets
        mapped to ``None`` are left out
    :returns: mapped presets, by preset name, or ``None``, if there is no
        ``CMakePresets.json``
    """
    presets = Presets().visit_file(Path("CMakePresets.json"))
    if presets is None:
        return None

    cwd = Path.cwd()
    result: dict[str, T] = {}
    for preset in presets.values():
        mapped = mapper(preset, cwd)
        if mapped is None:
            continue
        result[preset.name] = mapped

    return result
