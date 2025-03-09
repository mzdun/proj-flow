# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)


import sys
import typing
from io import StringIO


class Capture:
    _stdout: typing.TextIO
    _stderr: typing.TextIO
    _io_stdout: StringIO
    _io_stderr: StringIO
    stdout: str = ""
    stderr: str = ""

    def __enter__(self):
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = self._io_stdout = StringIO()
        sys.stderr = self._io_stderr = StringIO()
        return self

    def __exit__(self, exc_type, *_exc):
        self.stdout = self._io_stdout.getvalue()
        self.stderr = self._io_stderr.getvalue()
        del self._io_stdout
        del self._io_stderr
        sys.stdout = self._stdout
        sys.stderr = self._stderr

        return exc_type is None or exc_type is SystemExit
