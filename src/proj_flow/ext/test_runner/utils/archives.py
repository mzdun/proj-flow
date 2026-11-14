# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.test_runner.utils.archives** unpacks the tar and zip archives used by the
``unpack`` test command.
"""

import os
import tarfile
import zipfile
from typing import Callable


def _untar(src, dst):
    with tarfile.open(src) as TAR:

        def is_within_directory(directory, target):
            abs_directory = os.path.abspath(directory)
            abs_target = os.path.abspath(target)

            # commonpath compares whole path components, so "/out2" is not
            # treated as being inside "/out"
            try:
                prefix = os.path.commonpath([abs_directory, abs_target])
            except ValueError:  # e.g. different drives on Windows
                return False

            return prefix == abs_directory

        for member in TAR.getmembers():
            member_path = os.path.join(dst, member.name)
            if not is_within_directory(dst, member_path):
                raise Exception(f"Attempted path traversal in Tar file: {member.name}")

        TAR.extractall(dst)


def _unzip(src, dst):
    with zipfile.ZipFile(src) as ZIP:
        ZIP.extractall(dst)


_tar = (_untar, ["tar", "-xf"])

Unpacker = Callable[[str, str], None]
UnpackInfo = tuple[Unpacker, list[str]]

ARCHIVES: dict[str, UnpackInfo] = {
    ".tar": _tar,
    ".tgz": _tar,
    ".zip": (_unzip, ["unzip"]),
}


def locate_unpack(archive: str) -> UnpackInfo:
    """
    Selects the unpacker for given archive, based on its extension. Any
    archive with ``.tar`` as the next-to-last extension (e.g.
    ``.tar.gz``, ``.tar.xz``) or with ``.tgz`` extension is treated as
    a tarball.

    :param archive: path to the archive
    :returns: the Python unpacker function, taking source and destination
        paths, together with matching command line
    :raises ValueError: if the extension is not supported
    """
    reminder, ext = os.path.splitext(archive)
    _, mid = os.path.splitext(reminder)
    if mid == ".tar":
        ext = ".tar"
    try:
        return ARCHIVES[ext]
    except KeyError:
        known = ", ".join(sorted(ARCHIVES))
        raise ValueError(
            f"{archive}: unsupported archive type; known types: {known}"
        ) from None


del _tar
del _unzip
del _untar
