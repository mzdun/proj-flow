# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.test_runner.driver.env** defines :class:`Env`, the environment shared by all
test cases, which expands variables in test definitions and patches the paths
and versions in the outputs of the tested binary.
"""

import os
import random
import re
import string
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

from proj_flow.ext.test_runner.utils.io import ProcessIO


def _alt_sep(input: str, value: str, var: str):
    split = input.split(value)
    first = split[0]
    split = split[1:]
    for index in range(len(split)):
        m = re.match(r"^(\S+)((\n|.)*)$", split[index])
        if m is None:
            continue
        g2 = m.group(2)
        if g2 is None:
            g2 = ""
        split[index] = "{}{}".format(m.group(1).replace(os.sep, "/"), g2)
    return var.join([first, *split])


@dataclass
class Env:
    """
    Environment shared by all test cases in a single test run.
    """

    #: Path to the tested executable.
    target: str
    #: Name of the tested executable, without the extension on Windows; used
    #: to recognize the executable in the commands of a test.
    target_name: str
    #: Build directory, in which the tested executable was built.
    build_dir: str
    #: Directory with test data, using forward slashes; substituted for
    #: ``$DATA``.
    data_dir: str
    #: Directory with installed copy of the binaries; substituted for
    #: ``$INST``.
    inst_dir: str
    #: Temporary directory, using forward slashes; substituted for ``$TMP``.
    tempdir: str
    #: Version of the tested project; substituted for ``$VERSION``.
    version: str
    #: Width of the test counter in the progress lines.
    counter_digits: int
    #: Number of tests in the test run.
    counter_total: int
    #: Commands available in ``prepare`` and ``cleanup`` lists, mapping the
    #: command name to minimal number of arguments and a callback.
    handlers: dict[str, tuple[int, Callable[[Any, list[str]], None]]]
    #: Native spelling of :attr:`data_dir`, if different from the forward
    #: slash one.
    data_dir_alt: str | None = None
    #: Native spelling of :attr:`tempdir`, if different from the forward
    #: slash one.
    tempdir_alt: str | None = None
    # TODO: installable patches
    #: Regular expression patches applied to every output line, before the
    #: patches from the test itself.
    builtin_patches: dict[str, str] | None = None
    #: Prefix of the environment variables, which should be shown in the
    #: command line of a failed test.
    reportable_env_prefix: str | None = None

    def with_random_temp_subdir(self):
        """
        Creates a copy of this environment, with a randomly-named subdirectory
        of current temporary directory as the new temporary directory.

        :returns: Copy of the environment with updated :attr:`tempdir` and
            :attr:`tempdir_alt`.
        """
        temp_instance = "".join(random.choice(string.ascii_letters) for _ in range(16))
        tempdir = f"{self.tempdir}/{temp_instance}"
        tempdir_alt = None
        if self.tempdir_alt is not None:
            tempdir_alt = f"{self.tempdir_alt}{os.sep}{temp_instance}"

        return replace(self, tempdir=tempdir, tempdir_alt=tempdir_alt)

    def expand(
        self, input: str, tempdir: str, cwd: str, additional: dict[str, str] = {}
    ):
        """
        Replaces ``$TMP``, ``$CWD``, ``$DATA``, ``$INST`` and ``$VERSION``
        in the input with their values, then replaces ``$NAME`` for each
        name from the additional variables.

        :param input: text to expand
        :param tempdir: value for ``$TMP``
        :param cwd: value for ``$CWD``
        :param additional: additional variables, e.g. ones stored by the
            ``store`` command
        :returns: Expanded text.
        """
        input = (
            input.replace("$TMP", tempdir)
            .replace("$CWD", cwd)
            .replace("$DATA", self.data_dir)
            .replace("$INST", self.inst_dir)
            .replace("$VERSION", self.version)
        )
        for key, value in additional.items():
            input = input.replace(f"${key}", value)
        return input

    def patch_io(self, io: ProcessIO, cwd: str, patches: dict[str, str]):
        """
        Patches both output streams of a process with :meth:`patch`. On
        Windows, the line endings are normalized to ``\\n`` first.

        :param io: outputs of the tested process
        :param cwd: working directory of the test, to be replaced with
            ``$CWD``
        :param patches: regular expression patches from the test
        :returns: New process outputs with patched streams and the same
            return code.
        """
        stdout = io.stdout
        stderr = io.stderr
        if os.name == "nt":
            stdout = stdout.replace("\r\n", "\n")
            stderr = stderr.replace("\r\n", "\n")
        return ProcessIO(
            returncode=io.returncode,
            stdout=self.patch(stdout, cwd, patches),
            stderr=self.patch(stderr, cwd, patches),
        )

    def patch(self, input: str, cwd: str, patches: dict[str, str]):
        """
        Reverses :meth:`expand` on the output: replaces the working, temporary
        and data directories with ``$CWD``, ``$TMP`` and ``$DATA`` (turning
        path separators after them to ``/``) and the version with
        ``$VERSION``. Then, for each line matching a pattern from
        :attr:`builtin_patches` and later from ``patches``, replaces that
        line with the expanded replacement.

        :param input: text to patch
        :param cwd: working directory of the test
        :param patches: regular expression patches from the test
        :returns: Patched text.
        """
        input = _alt_sep(input, cwd, "$CWD")
        input = _alt_sep(input, self.tempdir, "$TMP")
        input = _alt_sep(input, self.data_dir, "$DATA")
        if self.version:
            input = input.replace(self.version, "$VERSION")

        if self.tempdir_alt is not None:
            input = _alt_sep(input, self.tempdir_alt, "$TMP")
            if self.data_dir_alt:
                input = _alt_sep(input, self.data_dir_alt, "$DATA")

        builtins = self.builtin_patches or {}

        lines = input.split("\n")
        for patch, replacement in builtins.items():
            pattern = re.compile(patch)
            for lineno in range(len(lines)):
                m = pattern.match(lines[lineno])
                if m:
                    lines[lineno] = m.expand(replacement)

        for patch, replacement in patches.items():
            pattern = re.compile(patch)
            for lineno in range(len(lines)):
                m = pattern.match(lines[lineno])
                if m:
                    lines[lineno] = m.expand(replacement)
        return "\n".join(lines)

    def source_dir(self):
        """
        Finds the source directory of the tested project, by looking it up
        in the ``CMakeCache.txt`` of the :attr:`build_dir`.

        :returns: Source directory from CMake cache, or the grandparent of
            the build directory, if the cache does not name one.
        """
        key = "CMAKE_HOME_DIRECTORY"
        build_dir = Path(self.build_dir)
        cmake_cache = build_dir / "CMakeCache.txt"
        try:
            lines = cmake_cache.read_text().split("\n")
            prefix = f"{key}:INTERNAL="
            for line in lines:
                if not line.startswith(prefix):
                    continue
                source_dir = line[len(prefix) :].strip()
                if source_dir and not source_dir.endswith("-NOTFOUND"):
                    return Path(source_dir)
        except FileNotFoundError:
            pass

        return build_dir.parent.parent
