# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import fnmatch
import os
import sys
from abc import abstractmethod
from typing import List, cast

from cxx_flow.flow import step
from cxx_flow.flow.config import Config, Runtime

if sys.platform == "win32":
    from . import win32

else:

    class win32:
        @staticmethod
        def is_active(*args):
            return False

        @staticmethod
        def sign(*args):
            return 0

        @staticmethod
        def is_pe_exec(arg):
            return False


def should_exclude(filename: str, exclude: List[str], config_os: str):
    basename = os.path.splitext(filename)[0] if config_os == "windows" else filename

    for pattern in exclude:
        if fnmatch.fnmatch(basename, pattern):
            return True

    return False


class SignBase(step.Step):
    def is_active(self, config: Config, rt: Runtime) -> int:
        return win32.is_active(config.os)

    @abstractmethod
    def get_files(self, config: Config, rt: Runtime) -> List[str]: ...

    def run(self, config: Config, rt: Runtime) -> int:
        files = [file.replace(os.sep, "/") for file in self.get_files(config, rt)]
        if len(files) == 0:
            return 0

        rt.print("signtool", *(os.path.basename(file) for file in files))

        if rt.dry_run:
            return 0

        return win32.sign(files)


class SignFiles(SignBase):
    name = "Sign"
    runs_after = ["Build"]

    def get_files(self, config: Config, rt: Runtime) -> List[str]:
        cfg = cast(dict, rt._cfg.get("binaries", {}))
        roots = cfg.get("directories", ["bin", "lib", "libexec", "share"])
        exclude = cfg.get("exclude", ["*-test"])

        result: List[str] = []
        build_dir = os.path.join("build", config.preset)
        for root in roots:
            for curr_dir, _, filenames in os.walk(os.path.join(build_dir, root)):
                for filename in filenames:
                    if should_exclude(filename, exclude, config.os):
                        continue

                    full_path = os.path.join(curr_dir, filename)
                    if not win32.is_pe_exec(full_path):
                        continue

                    result.append(full_path)
        return result


class SignMsi(SignBase):
    name = "SignPackages"
    runs_after = ["Pack"]

    def is_active(self, config: Config, rt: Runtime) -> int:
        return super().is_active(config, rt) and "WIX" in config.items.get(
            "cpack_generator", []
        )

    def get_files(self, config: Config, rt: Runtime) -> List[str]:
        result: List[str] = []
        pkg_dir = os.path.join("build", config.preset, "packages")
        for curr_dir, dirnames, filenames in os.walk(pkg_dir):
            dirnames[:] = []
            for filename in filenames:
                _, ext = os.path.splitext(filename)
                if ext.lower() != ".msi":
                    continue

                result.append(os.path.join(curr_dir, filename))

        return result


step.register_step(SignFiles())
step.register_step(SignMsi())
