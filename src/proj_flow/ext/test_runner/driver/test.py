# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
import random
import re
import shlex
import shutil
import string
import subprocess
import sys
from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from typing import Callable, TypeVar, cast

import yaml

try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader

_flds = ["Return code", "Standard out", "Standard err"]
_streams = ["stdout", "stderr"]


def _last_enter(value: str):
    if len(value) and value[-1] == "\n":
        value = value[:-1] + "\\n"
    return value + "\n"


def _diff(expected, actual):
    expected = _last_enter(expected).splitlines(keepends=False)
    actual = _last_enter(actual).splitlines(keepends=False)
    return "\n".join(list(unified_diff(expected, actual, lineterm=""))[2:])


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


def str_presenter(dumper: Dumper, data: str):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")

    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, str_presenter, Dumper=Dumper)


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
    handlers: dict[str, tuple[int, Callable[["Test", list[str]], None]]]
    data_dir_alt: str | None = None
    tempdir_alt: str | None = None
    # TODO: installable patches
    builtin_patches: dict[str, str] | None = None
    reportable_env_prefix: str | None = None

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

    def fix(self, raw_input: bytes, cwd: str, patches: dict[str, str]):
        if os.name == "nt":
            raw_input = raw_input.replace(b"\r\n", b"\n")
        input = raw_input.decode("UTF-8")
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


def _test_name(filename: Path) -> str:
    dirname = filename.parent.name
    basename = filename.stem

    def num(s: str):
        items = s.split("-")
        if len(items) < 2:
            return s
        items[0] = f"({items[0]})"
        return " ".join(items)

    return f"{num(dirname)} :: {num(basename)}"


def _paths(key: str, dirs: list[str]):
    vals = [val for val in os.environ.get(key, "").split(os.pathsep) if val != ""]
    named = f"${key}"
    if named in dirs:
        pos = dirs.index(named)
        copy = [*dirs]
        copy[pos:pos] = vals
        vals = copy
    else:
        vals.extend(dirs)
    return os.pathsep.join(vals)


StrOrBytes = TypeVar("StrOrBytes", str, bytes)


@dataclass
class FileContents[StrOrBytes]:
    filename: str
    path: Path
    content: StrOrBytes | None

    def decode(self):
        return FileContents[str](
            filename=self.filename,
            path=self.path,
            content=cast(bytes, self.content).decode() if self.content else None,
        )


def load_file_contents(filename: str, environment: Env, cwd: str):
    path = Path(environment.expand(filename, environment.tempdir, cwd=cwd))
    try:
        content = path.read_bytes()
    except FileNotFoundError:
        content = None
    return FileContents(filename=filename, path=path, content=content)


def fix_file_contents(
    self: FileContents[bytes], env: Env, cwd: str, patches: dict[str, str]
):
    return FileContents(
        filename=self.filename,
        path=self.path,
        content=env.fix(self.content, cwd, patches) if self.content else None,
    )


@dataclass
class FileWrite[StrOrBytes]:
    generated: FileContents[StrOrBytes]
    template: FileContents[StrOrBytes]
    save: bool

    def needs_saving(self):
        return self.template.content is None or self.save

    def copy_file(self):
        if not self.generated.content:
            return False

        self.template.path.parent.mkdir(parents=True, exist_ok=True)
        self.template.path.write_bytes(cast(str, self.generated.content).encode())
        return True


def fix_file_write(self: FileWrite[bytes], env: Env, cwd: str, patches: dict[str, str]):
    return FileWrite(
        generated=fix_file_contents(self.generated, env, cwd, patches),
        template=self.template.decode(),
        save=self.save,
    )


@dataclass
class Expected:
    returncode: int
    stdout: str
    stderr: str

    def as_dict(self):
        return {
            "return-code": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


class Test:
    cwd: str
    data: dict
    filename: Path
    name: str
    ok: bool
    post_args: list[list[str]]
    current_env: Env | None
    additional_env: dict[str, str]

    linear: bool
    disabled: bool | str
    lang: str
    args: list[str]
    post: list[list[str]]
    expected: Expected | None
    check: list[str]
    writes: dict[str, str | dict]
    patches: dict[str, str]
    env: dict[str, str | None]
    prepare: list[list[str]]
    cleanup: list[list[str]]

    def __init__(self, data: dict, filename: Path, count: int):
        self.cwd = os.getcwd()
        self.data = data
        self.filename = filename
        self.name = _test_name(filename)
        self.ok = True
        self.post_args = []
        self.current_env = None
        self.additional_env = {}

        self.linear = cast(bool, data.get("linear", False))
        self.disabled = cast(bool | str, data.get("disabled", False))
        self.lang = cast(str, data.get("lang", "en"))
        self.args = []
        self.post = []
        self.expected = None
        self.check = ["all"] * len(_streams)
        self.writes = cast(dict[str, str | dict], data.get("writes", {}))
        self.patches = cast(dict[str, str], data.get("patches", {}))
        self.env = {}
        self.prepare = []
        self.cleanup = []

        if isinstance(self.disabled, bool):
            self.ok = not self.disabled
        elif isinstance(self.disabled, str):
            self.ok = self.disabled != sys.platform

        rebuild = False

        _args = cast(str | list[str] | None, data.get("args"))
        if _args is None:
            self.ok = False
            return
        elif isinstance(_args, list):
            rebuild = True
            data["args"] = shlex.join(_args)
            self.args = _args
        else:
            self.args = shlex.split(_args)

        self.post_args, rebuild = self.__join_args("post", data, rebuild)

        if "expected" not in data:
            self.ok = False
            return

        _expected = cast(None | dict[str, str | list[str]], data.get("expected"))
        if isinstance(_expected, dict):
            returncode = cast(None | int, _expected.get("return-code"))
            stdout = _expected.get("stdout")
            stderr = _expected.get("stderr")
            if not (
                isinstance(returncode, int)
                and isinstance(stdout, (str, list))
                and isinstance(stderr, (str, list))
            ):
                self.ok = False
                return
            if isinstance(stdout, list):
                stdout = "\n".join(stdout)
            if isinstance(stderr, list):
                stderr = "\n".join(stderr)
            self.expected = Expected(
                returncode=returncode, stdout=stdout, stderr=stderr
            )

        _check = cast(dict[str, str], data.get("check", {}))
        for index in range(len(_streams)):
            self.check[index] = _check.get(_streams[index], self.check[index])

        _env = cast(dict[str, str | list[str] | None], data.get("env", {}))
        self.env = {
            key: _paths(key, value) if isinstance(value, list) else value
            for key, value in _env.items()
        }

        self.prepare, rebuild = self.__join_args("prepare", data, rebuild)
        self.cleanup, rebuild = self.__join_args("cleanup", data, rebuild)

        if rebuild:
            if self.expected:
                data["expected"] = self.expected.as_dict()
            self.store()

    def __join_args(self, key: str, data: dict, rebuild: bool):
        _rebuild = rebuild
        result: list[list[str]] = []

        lines = cast(str | list[str | list[str]], data.get(key, []))
        if isinstance(lines, str):
            lines = [lines]

        for index in range(len(lines)):
            cmd = lines[index]
            if isinstance(cmd, str):
                result.append(shlex.split(cmd))
                continue

            _rebuild = True
            data[key][index] = shlex.join(cmd)
            result.append(cmd)

        return result, _rebuild

    def run_cmds(self, env: Env, ops: list[list[str]], tempdir: str) -> bool | None:
        saved = self.current_env
        self.current_env = env
        try:
            for op in ops:
                orig = [*op]
                is_safe = False
                try:
                    name = op[0]
                    if name[:5] == "safe-":
                        name = name[5:]
                        is_safe = True
                    min_args, cb = env.handlers[name]
                    op = op[1:]
                    if len(op) < min_args:
                        return None
                    cb(self, [env.expand(o, tempdir, cwd=self.cwd) for o in op])
                except Exception as ex:
                    if op[0] != "safe-rm":
                        print("Problem while handling", shlex.join(orig))
                        print(ex)
                        raise
                    if is_safe:
                        continue
                    return None
        finally:
            self.current_env = saved
        return True

    def run(self, environment: Env) -> tuple[Expected, list[FileWrite[bytes]]] | None:
        root = os.path.join(
            "build",
            ".testing",
            "".join(random.choice(string.ascii_letters) for _ in range(16)),
        )
        root = self.cwd = os.path.join(self.cwd, root)
        os.makedirs(root, exist_ok=True)

        prep = self.run_cmds(environment, self.prepare, environment.tempdir)
        if prep is None:
            return None

        expanded = [
            environment.expand(arg, environment.tempdir, self.cwd, self.additional_env)
            for arg in self.args
        ]
        post_expanded = [
            [
                environment.expand(
                    arg, environment.tempdir, self.cwd, self.additional_env
                )
                for arg in cmd
            ]
            for cmd in self.post_args
        ]

        _env = {name: os.environ[name] for name in os.environ}
        _env["LANGUAGE"] = self.lang
        for key in self.env:
            value = self.env[key]
            if value:
                _env[key] = environment.expand(value, environment.tempdir, cwd=self.cwd)
            elif key in _env:
                del _env[key]

        cwd = None if self.linear else self.cwd
        proc: subprocess.CompletedProcess = subprocess.run(
            [environment.target, *expanded], capture_output=True, env=_env, cwd=self.cwd
        )
        returncode: int = proc.returncode
        test_stdout: bytes = proc.stdout
        test_stderr: bytes = proc.stderr

        for sub_expanded in post_expanded:
            if returncode != 0:
                break
            proc_post: subprocess.CompletedProcess = subprocess.run(
                [environment.target, *sub_expanded],
                capture_output=True,
                env=_env,
                cwd=cwd,
            )
            returncode = proc_post.returncode
            if len(test_stdout) and len(proc_post.stdout):
                test_stdout += b"\n"
            if len(test_stderr) and len(proc_post.stderr):
                test_stderr += b"\n"
            test_stdout += proc_post.stdout
            test_stderr += proc_post.stderr

        expected_files: list[FileWrite[bytes]] = []
        for key, value in self.writes.items():
            if isinstance(value, str):
                expected_files.append(
                    FileWrite(
                        generated=load_file_contents(key, environment, cwd=self.cwd),
                        template=load_file_contents(value, environment, cwd=self.cwd),
                        save=False,
                    )
                )
            elif isinstance(value, dict):
                path = cast(str | None, value.get("path"))
                save = cast(bool, value.get("save", False))
                if not isinstance(path, str) or not isinstance(save, bool):
                    continue

                expected_files.append(
                    FileWrite(
                        generated=load_file_contents(key, environment, cwd=self.cwd),
                        template=load_file_contents(path, environment, cwd=self.cwd),
                        save=save,
                    )
                )

        clean = self.run_cmds(environment, self.cleanup, environment.tempdir)
        if clean is None:
            return None

        return (
            Expected(
                returncode=returncode,
                stdout=environment.fix(test_stdout, self.cwd, self.patches),
                stderr=environment.fix(test_stderr, self.cwd, self.patches),
            ),
            expected_files,
        )

    def clip(self, actual: Expected) -> str | Expected:
        if not self.expected:
            return actual

        returncode, streams = actual.returncode, [actual.stdout, actual.stderr]
        expected = [self.expected.stdout, self.expected.stderr]

        for ndx in range(len(self.check)):
            check = self.check[ndx]
            if check != "all":
                ex = expected[ndx]
                ex_len = len(ex)
                if check == "begin":
                    if len(streams[ndx]) > ex_len:
                        streams[ndx] = streams[ndx][:ex_len]
                elif check == "end":
                    streams[ndx] = streams[ndx][-ex_len:]
                else:
                    return check
        return Expected(returncode=returncode, stdout=streams[0], stderr=streams[1])

    @staticmethod
    def text_diff(
        header: str, expected: str, actual: str, pre_mark: str = "", post_mark: str = ""
    ):
        return f"""{header}
  Expected:
    {pre_mark}{repr(expected)}{post_mark}
  Actual:
    {pre_mark}{repr(actual)}{post_mark}

Diff:
{_diff(expected, actual)}
"""

    def report_io(self, actual: Expected):
        result = ""
        if not self.expected:
            return result

        if actual.returncode != self.expected.returncode:
            result += f"""{_flds[0]}
  Expected:
    {repr(self.expected.returncode)}
  Actual:
    {repr(actual.returncode)}
"""
        streams = [
            (_flds[1], self.check[0], actual.stdout, self.expected.stdout),
            (_flds[2], self.check[1], actual.stderr, self.expected.stderr),
        ]
        for header, check, actual_stream, expected_stream in streams:
            if actual_stream == expected_stream:
                continue

            if result:
                result += "\n"

            pre_mark = "..." if check == "end" else ""
            post_mark = "..." if check == "begin" else ""
            result += Test.text_diff(
                header,
                expected_stream,
                actual_stream,
                pre_mark,
                post_mark,
            )

        return result

    def report_file(
        self,
        file: FileWrite[str],
    ):
        header = file.generated.filename

        if not file.generated.content:
            header += "\n  New file was not present to be read"
        if not file.generated.content:
            header += (
                f"\n  Test file {file.generated.filename} was not present to be read"
            )

        if not file.generated.content or not file.template.content:
            return header

        return Test.text_diff(
            header,
            expected=file.template.content,
            actual=file.generated.content,
        )

    def test_footer(self, env: Env, tempdir: str):
        _env = {}
        _env["LANGUAGE"] = self.lang
        for key in self.env:
            value = self.env[key]
            if value:
                _env[key] = value
            elif key in _env:
                del _env[key]
        if env.reportable_env_prefix:
            for key in os.environ:
                if key.startswith(env.reportable_env_prefix) and key not in _env:
                    _env[key] = os.environ[key]

        expanded = [env.expand(arg, tempdir, cwd=self.cwd) for arg in self.args]
        call = " ".join(
            shlex.quote(arg.replace(os.sep, "/"))
            for arg in [
                *["{}={}".format(key, val) for key, val in _env.items()],
                env.target,
                *expanded,
            ]
        )
        return f"{call}\ncwd: {self.cwd}\ntest: {self.filename}"

    def nullify(self, lang: str | None):
        if lang is not None:
            self.lang = lang
            self.data["lang"] = lang
        self.expected = None
        self.data["expected"] = None
        self.store()

    def store(self):
        with self.filename.open("wb") as f:
            yaml.dump(
                self.data,
                stream=f,
                Dumper=Dumper,
                width=1024,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
                encoding="UTF-8",
            )

    def path(self, filename):
        return os.path.join(self.cwd, filename)

    def chdir(self, sub):
        self.cwd = os.path.abspath(os.path.join(self.cwd, sub))
        if self.linear:
            os.chdir(self.cwd)

    def ls(self, sub):
        name = self.path(sub)
        for _, dirnames, filenames in os.walk(name):
            names = sorted(
                [
                    *((name.lower(), f"{name}/") for name in dirnames),
                    *((name.lower(), f"{name}") for name in filenames),
                ]
            )
            dirnames[:] = []
            for _, name in names:
                print(name)

    def rmtree(self, sub):
        shutil.rmtree(self.path(sub))

    def cp(self, src: str, dst: str):
        shutil.copy2(self.path(src), self.path(dst))

    def makedirs(self, sub):
        os.makedirs(self.path(sub), exist_ok=True)

    def store_output(self, name: str, args: list[str]):
        env = self.current_env

        if env is not None and args[0] == env.target_name:
            args[0] = env.target

        proc = subprocess.run(args, shell=False, capture_output=True, cwd=self.cwd)
        self.additional_env[name] = proc.stdout.decode("UTF-8").strip()
        print(f"export {name}={self.additional_env[name]}")

    @staticmethod
    def load(filename: Path, count: int):
        with open(filename, encoding="UTF-8") as f:
            return Test(yaml.load(f, Loader=Loader), filename, count)
