# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from proj_flow.ext.test_runner.driver.env import Env


@dataclass
class FileContents:
    filename: str
    path: Path
    content: str | bytes | None

    @property
    def empty(self):
        return self.content is None

    @property
    def binary(self):
        return isinstance(self.content, bytes)

    def patched(self, env: Env, cwd: str, patches: dict[str, str]):
        if not isinstance(self.content, str):
            return self
        patched = env.patch(self.content, cwd, patches)
        return FileContents(filename=self.filename, path=self.path, content=patched)


def load_file_contents(filename: str, environment: Env, cwd: str):
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
    generated: FileContents
    template: FileContents
    save: bool

    @property
    def binary(self):
        return self.generated.binary or self.template.binary

    @property
    def needs_saving(self):
        return self.template.content is None or self.save

    def patched(self, env: Env, cwd: str, patches: dict[str, str]):
        return FileWrite(
            generated=self.generated.patched(env, cwd, patches),
            template=self.template,
            save=self.save,
        )

    def copy_file(self):
        if not self.generated.content:
            return False

        self.template.path.parent.mkdir(parents=True, exist_ok=True)
        self.template.path.write_bytes(cast(str, self.generated.content).encode())
        return True

    @staticmethod
    def load(generated_path: str, template_path: str, env: Env, cwd: str, save: bool):
        generated = load_file_contents(generated_path, env, cwd=cwd)
        template = load_file_contents(template_path, env, cwd=cwd)
        return FileWrite(generated=generated, template=template, save=save)
