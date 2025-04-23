# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import io
import json
import os
import unittest.mock
from typing import Dict, List, Optional, Tuple, Union

FsData = Dict[str, Union[dict, str, bytes]]


class BytesIO(io.BytesIO):
    files: FsData
    path: str

    def __init__(self, files: FsData, path: str, initial_bytes=b""):
        super().__init__(initial_bytes)
        self.files = files
        self.path = path

    def close(self):
        self.files[self.path] = self.getvalue()
        super().close()


class StringIO(io.StringIO):
    files: FsData
    path: str

    def __init__(
        self,
        files: FsData,
        path: str,
        initial_value: str | None = "",
        newline: str | None = "\n",
    ):
        super().__init__(initial_value, newline)
        self.files = files
        self.path = path

    def close(self):
        self.files[self.path] = self.getvalue()
        super().close()


def _read_file(files: FsData, path: str, encoding: Optional[str] = None):
    if path not in files:
        raise FileNotFoundError()
    data = files[path]
    text = data if isinstance(data, (str, bytes)) else json.dumps(data)
    if encoding is None:
        return io.BytesIO(text.encode() if isinstance(text, str) else text)
    return io.StringIO(text.decode() if isinstance(text, bytes) else text, newline="\n")


def fs(files: FsData):
    def wrap(
        path: str, mode: Optional[str] = None, /, *, encoding: Optional[str] = None
    ):
        if mode in [None, "r", "rb", "a", "ab"]:
            return _read_file(files, path, encoding)

        if encoding is None:
            return BytesIO(files, path)

        return StringIO(files, path, newline="\n")

    return wrap


DirEntry = Union[bool, "Directory"]
Directory = Dict[str, DirEntry]
WalkEntry = Tuple[str, List[str], List[str]]
PartialReturn = Tuple[str, Directory]


def _locate(filesystem: Directory, path: str, for_mkdirs=False):
    nav = path.replace(os.sep, "/").split("/")
    context: DirEntry = filesystem
    here = {".", ""}
    for step in nav:
        if step in here:
            continue
        if not isinstance(context, dict):
            return None
        if step not in context:
            if not for_mkdirs:
                return None
            context[step] = {}

        context = context[step]

    return context


def walk_mock(filesystem: Directory):
    def wrap(root: str):
        breadth: List[str] = [root]

        while breadth:
            path = breadth[0]
            breadth = breadth[1:]
            entry = _locate(filesystem, path)
            if not isinstance(entry, dict):
                continue

            files = [
                name for name, entry in entry.items() if not isinstance(entry, dict)
            ]
            dirs = [name for name, entry in entry.items() if isinstance(entry, dict)]

            yield (path, dirs, files)

            breadth.extend(map(lambda dirname: os.path.join(path, dirname), dirs))

    return wrap


def isdir_mock(filesystem: Directory):
    def wrap(path: str):
        entry = _locate(filesystem, path)
        return isinstance(entry, dict)

    return wrap


def isfile_mock(filesystem: Directory):
    def wrap(path: str):
        entry = _locate(filesystem, path)
        return isinstance(entry, bool)

    return wrap


def mkdirs_mock(filesystem: Directory):
    def wrap(path: str, *_args, **_kwargs):
        _locate(filesystem, path, for_mkdirs=True)

    return wrap


OS_PATH_ABSPATH = "os.path.abspath"
OS_PATH_ISDIR = "os.path.isdir"
OS_PATH_ISFILE = "os.path.isfile"
OS_MAKEDIRS = "os.makedirs"
OS_WALK = "os.walk"

OS_MOCK_WRAPS = {
    OS_PATH_ABSPATH: lambda _: lambda s: s,
    OS_PATH_ISDIR: isdir_mock,
    OS_PATH_ISFILE: isfile_mock,
    OS_MAKEDIRS: mkdirs_mock,
    OS_WALK: walk_mock,
}


def wrap_fs(filesystem: Directory, mocker, *mocks: str):
    result: Dict[str, unittest.mock.Mock] = {}

    for name in mocks:
        wrapper = OS_MOCK_WRAPS.get(name)
        if not wrapper:
            raise KeyError(name)
        result[name] = mocker.patch(name, wraps=wrapper(filesystem))

    return result
