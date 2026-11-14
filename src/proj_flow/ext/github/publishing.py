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


def build_regex(project: release.Project):
    """
    Build the regular expression matching the package file names of the
    project, i.e. names starting with the project's package prefix and ending
    with its package suffix.

    :param project: project to build the expression for
    :returns: compiled expression, with the text between the prefix and the
        suffix in the first group
    """
    regexPre = re.escape(project.package_prefix)
    regexPost = re.escape(project.package_suffix)
    regex = f"^{regexPre}(.*){regexPost}$"
    return re.compile(regex)


def gather_artifacts(directory: str, matcher: re.Pattern):
    """
    Find the release artifacts. If ``directory`` is a directory, the names of
    the files directly inside it (not in subdirectories) are matched.
    Otherwise, ``directory`` is treated as a ZIP archive and the matching
    entries are extracted to ``<directory>-dir``.

    :param directory: directory or ZIP archive with the artifacts
    :param matcher: expression the artifact names must match, e.g. from
        :func:`build_regex`
    :returns: tuple of the directory with the artifacts and the list of
        their names
    """
    names: list[str] = []
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
    """
    Write the SHA-256 checksums of the artifacts to a file in
    ``sha256sum -b`` format and add that file's name to ``names``. In dry
    run, the file is not written, but the name is still added.

    :param rt: runtime used for printing and dry run check
    :param directory: directory with the artifacts
    :param names: names of the artifacts, extended in place with
        ``outname``
    :param outname: name of the checksum file, created in ``directory``
    """
    rt.print("sha256sum", "-b")
    if not rt.dry_run:
        with open(os.path.join(directory, outname), "w") as output:
            for name in names:
                digest = _hash(os.path.join(directory, name))
                print(f"{digest} *{name}", file=output)
    names.append(outname)
