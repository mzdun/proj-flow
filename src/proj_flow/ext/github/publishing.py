# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.github.publishing** provides utilities for ``github
publish`` command.
"""


import hashlib
import io
import os
import re
import typing
import zipfile

from proj_flow.api import env, release


def _safe_regex(value: str) -> str:
    for esc in "\\.+*?()[]":
        value = value.replace(esc, f"\\{esc}")
    return value


def build_regex(project: release.Project):
    regexPre = _safe_regex(project.package_prefix)
    regexPost = _safe_regex(project.package_suffix)
    regex = f"^{regexPre}(.*){regexPost}$"
    return re.compile(regex)


def gather_artifacts(directory: str, matcher: re.Pattern):
    if os.path.isdir(directory):
        for _, dirnames, filenames in os.walk(directory):
            dirnames[:] = []
            names = [name for name in filenames if matcher.match(name)]
    else:
        next_directory = f"{directory}-dir"
        os.makedirs(next_directory, exist_ok=True)
        with zipfile.ZipFile(directory) as zip:
            names = [name for name in zip.namelist() if matcher.match(name)]
            for name in names:
                zip.extract(name, path=next_directory)
        directory = next_directory

    return directory, names


def _hash(filename: str) -> str:
    sha = hashlib.sha256()
    with open(filename, "rb") as data:
        for block in iter(lambda: data.read(io.DEFAULT_BUFFER_SIZE), b""):
            sha.update(block)
    return sha.hexdigest()


def checksums(rt: env.Runtime, directory: str, names: typing.List[str], outname: str):
    rt.print("sha256sum", "-b")
    if not rt.dry_run:
        with open(os.path.join(directory, outname), "w") as output:
            for name in names:
                digest = _hash(os.path.join(directory, name))
                print(f"{digest} *{name}", file=output)
    names.append(outname)
