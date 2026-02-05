# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
import random
import re
import string
from dataclasses import dataclass, replace
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
    target: str
    target_name: str
    build_dir: str
    data_dir: str
    inst_dir: str
    tempdir: str
    version: str
    counter_digits: int
    counter_total: int
    handlers: dict[str, tuple[int, Callable[[Any, list[str]], None]]]
    data_dir_alt: str | None = None
    tempdir_alt: str | None = None
    # TODO: installable patches
    builtin_patches: dict[str, str] | None = None
    reportable_env_prefix: str | None = None

    def with_random_temp_subdir(self):
        temp_instance = "".join(random.choice(string.ascii_letters) for _ in range(16))
        tempdir = f"{self.tempdir}/{temp_instance}"
        tempdir_alt = None
        if self.tempdir_alt is not None:
            tempdir_alt = f"{self.tempdir_alt}{os.sep}{temp_instance}"

        return replace(self, tempdir=tempdir, tempdir_alt=tempdir_alt)

    def expand(
        self, input: str, tempdir: str, cwd: str, additional: dict[str, str] = {}
    ):
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
        input = _alt_sep(input, cwd, "$CWD")
        input = _alt_sep(input, self.tempdir, "$TMP")
        input = _alt_sep(input, self.data_dir, "$DATA")
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
