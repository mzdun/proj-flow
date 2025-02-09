# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.cplusplus.conan._conan** adds support for both Conan v1
and v2.
"""

import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Callable, List, cast

from proj_flow.api.env import Config, Runtime
from proj_flow.base import cmd
from proj_flow.dependency import VER_REGEX


class conan(ABC):
    version: int

    def __init__(self, version: int = 1):
        self.version = version

    def settings(self, cfg: Config):
        result: List[str] = []
        for threshold, name in enumerate(
            ["conan_settings", "conan2_settings"],
        ):
            if self.version <= threshold:
                break
            result = cast(List[str], cfg.items.get(name, result))
        return result

    @abstractmethod
    def config(
        self,
        rt: Runtime,
        conan_output_dir: str,
        compiler_profile_name: str,
        build_type_profile_name: str,
    ) -> int: ...


class conan_1(conan):
    def __init__(self):
        super().__init__(1)

    def config(
        self,
        rt: Runtime,
        conan_output_dir: str,
        compiler_profile_name: str,
        build_type_profile_name: str,
    ) -> int:
        if rt.cmd(
            "conan",
            "profile",
            "new",
            "--detect",
            "--force",
            compiler_profile_name,
        ):
            return 1

        return rt.cmd(
            "conan",
            "install",
            "-if",
            conan_output_dir,
            "-of",
            conan_output_dir,
            "--build",
            "missing",
            "-pr:b",
            build_type_profile_name,
            "-pr:h",
            build_type_profile_name,
            ".",
        )


class conan_2(conan):
    def __init__(self):
        super().__init__(2)

    def config(
        self,
        rt: Runtime,
        conan_output_dir: str,
        compiler_profile_name: str,
        build_type_profile_name: str,
    ) -> int:
        if rt.cmd(
            "conan",
            "profile",
            "detect",
            "--force",
            "--name",
            compiler_profile_name,
        ):
            return 1

        return rt.cmd(
            "conan",
            "install",
            "-of",
            conan_output_dir,
            "--build",
            "missing",
            "-pr:b",
            build_type_profile_name,
            "-pr:h",
            build_type_profile_name,
            ".",
        )


def _conan_version():
    found = shutil.which("conan")
    if found is None:
        return 1

    proc = cast(
        subprocess.CompletedProcess[str],
        cmd.run(found, "--version", capture_output=True),
    )
    if proc.returncode != 0:
        return 1
    m = VER_REGEX.search(proc.stdout)
    version = m.group(0) if m is not None else None
    if version is None:
        return 1
    chunks = [int(v.strip()) for v in version.split(".")]
    if len(chunks) < 1:
        return 1
    return chunks[0]


ctors: List[Callable[[], conan]] = [
    conan_1,
    conan_2,
]


def conan_api() -> conan:
    version = _conan_version()
    index = version - 1
    if index >= len(ctors):
        return ctors[-1]()
    return ctors[index]()
