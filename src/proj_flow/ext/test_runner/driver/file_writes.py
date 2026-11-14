# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.test_runner.driver.file_writes** represents the files written by the
tested binary, together with their expected contents.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

from proj_flow.ext.test_runner.driver.env import Env


@dataclass
class FileContents:
    """
    Contents of a single file, either written by the tested binary, or
    expected by the test.
    """

    #: Name of the file, as given in the test, before expansion.
    filename: str
    #: Expanded path to the file.
    path: Path
    #: Text of the file, raw bytes, if the file is not valid UTF-8, or
    #: ``None``, if the file could not be found.
    content: str | bytes | None

    @property
    def empty(self):
        """``True``, if the file was not found."""
        return self.content is None

    @property
    def binary(self):
        """``True``, if the file was not a valid UTF-8 text."""
        return isinstance(self.content, bytes)

    def patched(self, env: Env, cwd: str, patches: dict[str, str]):
        """
        Patches the text contents of the file with :meth:`Env.patch
        <proj_flow.ext.test_runner.driver.env.Env.patch>`.

        :param env: environment of the test run
        :param cwd: working directory of the test
        :param patches: regular expression patches from the test
        :returns: New file contents with patched text, or this object, if the
            contents are binary or missing.
        """
        if not isinstance(self.content, str):
            return self
        patched = env.patch(self.content, cwd, patches)
        return FileContents(filename=self.filename, path=self.path, content=patched)


def load_file_contents(filename: str, environment: Env, cwd: str):
    """
    Loads a file named in a test. Contents, which are valid UTF-8, are loaded
    as text, with all ``\\r`` removed on Windows; other contents are kept as
    bytes.

    :param filename: name of the file, possibly with ``$`` variables
    :param environment: environment used to expand the file name
    :param cwd: working directory of the test, for ``$CWD``
    :returns: Contents of the file, with ``content`` set to ``None``, if the
        file does not exist.
    """
    path = Path(environment.expand(filename, environment.tempdir, cwd=cwd))
    try:
        blob = path.read_bytes()
        try:
            text = blob.decode()
        except UnicodeError:
            text = None

        if text is None:
            return FileContents(filename=filename, path=path, content=blob)
        else:
            if sys.platform == "win32":
                text = text.replace("\r", "")
            return FileContents(
                filename=filename,
                path=path,
                content=text,
            )
    except FileNotFoundError:
        return FileContents(filename=filename, path=path, content=None)


@dataclass
class FileWrite:
    """
    File written by the tested binary, paired with the file holding its
    expected contents.
    """

    #: File written by the tested binary.
    generated: FileContents
    #: File with expected contents, stored next to the test.
    template: FileContents
    #: If ``True``, the expected file should always be overwritten with the
    #: generated one.
    save: bool

    @property
    def binary(self):
        """``True``, if either of the files is binary."""
        return self.generated.binary or self.template.binary

    @property
    def needs_saving(self):
        """``True``, if expected file is missing or the test asks to save it."""
        return self.template.content is None or self.save

    def patched(self, env: Env, cwd: str, patches: dict[str, str]):
        """
        Patches the generated file with :meth:`FileContents.patched`, leaving
        the expected file as-is.

        :param env: environment of the test run
        :param cwd: working directory of the test
        :param patches: regular expression patches from the test
        :returns: New file pair with patched generated contents.
        """
        return FileWrite(
            generated=self.generated.patched(env, cwd, patches),
            template=self.template,
            save=self.save,
        )

    def copy_file(self):
        """
        Writes the generated contents into the expected file, creating parent
        directories as needed.

        :returns: ``True``, if the file was written, ``False``, if the
            generated file was missing.
        """
        content = self.generated.content
        if content is None:
            return False

        self.template.path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            content = content.encode()
        self.template.path.write_bytes(content)
        return True

    @staticmethod
    def load(generated_path: str, template_path: str, env: Env, cwd: str, save: bool):
        """
        Loads both files with :func:`load_file_contents`.

        :param generated_path: name of the file written by the tested binary
        :param template_path: name of the file with expected contents
        :param env: environment used to expand the file names
        :param cwd: working directory of the test
        :param save: value for :attr:`save`
        :returns: New file pair.
        """
        generated = load_file_contents(generated_path, env, cwd=cwd)
        template = load_file_contents(template_path, env, cwd=cwd)
        return FileWrite(generated=generated, template=template, save=save)
