# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.sign** provides the ``"Sign"`` and ``"SignPackages"``
steps.
"""

import fnmatch
import os
import sys
from abc import abstractmethod
from typing import List, cast

from proj_flow.api import env, init, step

from . import api, win32


def should_exclude(filename: str, exclude: List[str], config_os: str):
    """
    Check, if the file matches any of the exclude patterns. On Windows, the
    extension is removed before matching, so ``*-test`` matches
    ``unit-test.exe``.

    :param filename: name of the file
    :param exclude: list of :func:`fnmatch.fnmatch` patterns
    :param config_os: OS of current config, e.g. ``"windows"``
    :returns: ``True``, if the file should not be signed
    """
    basename = os.path.splitext(filename)[0] if config_os == "windows" else filename

    for pattern in exclude:
        if fnmatch.fnmatch(basename, pattern):
            return True

    return False


class SignBase(step.Step):
    """
    Base of the signing steps, which sign files with the signing tools
    active on current platform.

    :param name: name of the step
    :param runs_after: names of the steps this one runs after
    :param runs_before: names of the steps this one runs before
    """

    _name: str
    _runs_after: List[str] = []
    _runs_before: List[str] = []

    _active_tools: List[api.SigningTool] = []

    @property
    def name(self):
        return self._name

    @property
    def runs_after(self):
        return self._runs_after

    @property
    def runs_before(self):
        return self._runs_before

    def __init__(
        self, name: str, runs_after: List[str] = [], runs_before: List[str] = []
    ):
        super().__init__()
        self._name = name
        self._runs_after = runs_after
        self._runs_before = runs_before

    def is_active(self, config: env.Config, rt: env.Runtime) -> bool:
        self._active_tools = [
            tool for tool in api.signing_tool.get() if tool.is_active(config, rt)
        ]
        return len(self._active_tools) > 0

    @abstractmethod
    def get_files(
        self, tool: api.SigningTool, config: env.Config, rt: env.Runtime
    ) -> List[str]:
        """
        List the files this step should sign with given tool.

        :param tool: one of the signing tools active in this run
        :param config: config of current run
        :param rt: runtime of current run
        :returns: paths of the files accepted by
            :meth:`~proj_flow.ext.sign.api.SigningTool.is_signable`
        """
        ...

    def run(self, config: env.Config, rt: env.Runtime) -> None:
        for tool in self._active_tools:
            files = [
                file.replace(os.sep, "/") for file in self.get_files(tool, config, rt)
            ]

            if len(files) == 0:
                continue

            tool.sign(config, rt, files)


@step.register
class SignFiles(SignBase):
    """*(Windows)* Signs executable files in build directory"""

    def __init__(self):
        super().__init__(name="Sign", runs_after=["Build"], runs_before=["Pack"])

    def get_files(
        self, tool: api.SigningTool, config: env.Config, rt: env.Runtime
    ) -> List[str]:
        """
        List the signable binaries in ``bin``, ``lib``, ``libexec`` and
        ``share`` subdirectories of the build directory, or in the
        directories from ``sign.directories`` in the config file. Files
        matching ``sign.exclude`` patterns (defaulting to ``["*-test"]``) are
        skipped.

        :param tool: one of the signing tools active in this run
        :param config: config of current run
        :param rt: runtime of current run
        :returns: paths of the files accepted by
            :meth:`~proj_flow.ext.sign.api.SigningTool.is_signable`
        """
        cfg = cast(dict, rt._cfg.get("sign", {}))
        roots = cfg.get("directories", ["bin", "lib", "libexec", "share"])
        exclude = cfg.get("exclude", ["*-test"])

        result: List[str] = []
        build_dir = config.build_dir
        for root in roots:
            for curr_dir, _, filenames in os.walk(os.path.join(build_dir, root)):
                for filename in filenames:
                    if should_exclude(filename, exclude, config.os):
                        continue

                    full_path = os.path.join(curr_dir, filename)
                    if tool.is_signable(full_path, as_package=False):
                        result.append(full_path)
        return result


@step.register
class SignMsi(SignBase):
    """*(Windows)* Signs MSI installers in build directory"""

    def __init__(self):
        super().__init__(
            name="SignPackages",
            runs_after=["Pack"],
            runs_before=["StorePackages", "Store"],
        )

    def is_active(self, config: env.Config, rt: env.Runtime) -> bool:
        return super().is_active(config, rt) and "WIX" in config.items.get(
            "cpack_generator", []
        )

    def get_files(
        self, tool: api.SigningTool, config: env.Config, rt: env.Runtime
    ) -> List[str]:
        """
        List the signable packages directly inside the ``packages``
        subdirectory of the build directory.

        :param tool: one of the signing tools active in this run
        :param config: config of current run
        :param rt: runtime of current run
        :returns: paths of the files accepted by
            :meth:`~proj_flow.ext.sign.api.SigningTool.is_signable`
        """
        result: List[str] = []
        pkg_dir = os.path.join(config.build_dir, "packages")
        for curr_dir, dirnames, filenames in os.walk(pkg_dir):
            dirnames[:] = []
            for filename in filenames:
                full_path = os.path.join(curr_dir, filename)
                if tool.is_signable(full_path, as_package=True):
                    result.append(full_path)

        return result


class SignInit(init.InitStep):
    """Adds ``/signature.key`` to ``.gitignore`` of new projects."""

    def postprocess(self, rt: env.Runtime, context: dict) -> None:
        try:
            with open(".gitignore", encoding="UTF-8") as ignoref:
                if "/signature.key" in ignoref.read().splitlines():
                    return
        except FileNotFoundError:
            pass
        with open(".gitignore", "ab") as ignoref:
            ignoref.write("\n/signature.key\n".encode("UTF-8"))


init.register_init_step(SignInit())
