# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.test_runner.driver.test** defines :class:`Test`, a single test case loaded
from a test file, with means to run it and report the differences between the
expected and actual results.
"""

import os
import random
import shlex
import shutil
import string
import subprocess
import sys
from difflib import unified_diff
from pathlib import Path
from typing import cast

import yaml

from proj_flow.ext.test_runner.driver.env import Env
from proj_flow.ext.test_runner.driver.file_writes import FileWrite
from proj_flow.ext.test_runner.utils.io import ProcessIO

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


def str_presenter(dumper: Dumper, data: str):
    """
    YAML representer for strings, which uses the literal block style for
    multiline strings, keeping the stored test files readable.

    :param dumper: YAML dumper writing the node
    :param data: string to represent
    :returns: Scalar node for the string.
    """
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")

    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, str_presenter, Dumper=Dumper)


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


class Test:
    """
    Single test case, loaded from a test file.

    :param data: parsed contents of the test file
    :param filename: path to the test file
    :param count: position of the test in the test suite; currently unused
    """

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
    input: str | None
    post: list[list[str]]
    expected: ProcessIO | None
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
        self.input = None
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

        test_input = cast(str | list[str] | None, data.get("input"))
        if isinstance(test_input, list):
            test_input = "\n".join(test_input)
        self.input = test_input

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
            self.expected = ProcessIO(
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
        """
        Runs ``prepare`` or ``cleanup`` commands through :attr:`Env.handlers
        <proj_flow.ext.test_runner.driver.env.Env.handlers>`, with expanded
        arguments. While running, ``env`` is available as
        :attr:`current_env`. Exceptions from a command prefixed with
        ``safe-``, e.g. ``safe-rm``, are ignored; other exceptions are printed
        and re-raised.

        :param env: environment of the test run
        :param ops: list of commands, each a list of the name and arguments
        :param tempdir: value for ``$TMP``
        :returns: ``True``, if all commands were run, ``None``, if a command
            had too few arguments.
        """
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
                    cb(
                        self,
                        [
                            env.expand(o, tempdir, self.cwd, self.additional_env)
                            for o in op
                        ],
                    )
                except Exception as ex:
                    if is_safe:
                        continue
                    print("Problem while handling", shlex.join(orig))
                    print(ex)
                    raise
        finally:
            self.current_env = saved
        return True

    def run(self, environment: Env) -> tuple[ProcessIO, list[FileWrite]] | None:
        """
        Runs the test. Moves :attr:`cwd` to a new random directory under
        ``build/.testing``, runs ``prepare`` commands, the tested binary with
        expanded ``args`` (and ``input``, if any), then each ``post`` call
        for as long as the return code stays zero, loads the files listed in
        ``writes`` and runs ``cleanup`` commands.

        :param environment: environment of the test run
        :returns: Patched outputs of all calls and the files to compare, or
            ``None``, if ``prepare`` or ``cleanup`` failed.
        """
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

        io = ProcessIO()
        kwargs = {}
        if self.input is not None:
            kwargs["input"] = self.input.encode()
        proc = subprocess.run(
            [environment.target, *expanded],
            capture_output=True,
            env=_env,
            cwd=self.cwd,
            **kwargs,
        )
        io.append(proc)

        for sub_expanded in post_expanded:
            if io.returncode != 0:
                break
            proc: subprocess.CompletedProcess = subprocess.run(
                [environment.target, *sub_expanded],
                capture_output=True,
                env=_env,
                cwd=self.cwd,
            )
            io.append(proc)

        expected_files: list[FileWrite] = []
        for key, value in self.writes.items():
            if isinstance(value, str):
                expected_files.append(
                    FileWrite.load(key, value, environment, cwd=self.cwd, save=False)
                )
            elif isinstance(value, dict):
                path = cast(str | None, value.get("path"))
                save = cast(bool, value.get("save", False))
                if not isinstance(path, str) or not isinstance(save, bool):
                    continue

                expected_files.append(
                    FileWrite.load(key, path, environment, cwd=self.cwd, save=save)
                )

        clean = self.run_cmds(environment, self.cleanup, environment.tempdir)
        if clean is None:
            return None

        return (
            environment.patch_io(io, self.cwd, self.patches),
            expected_files,
        )

    def clip(self, actual: ProcessIO) -> str | ProcessIO:
        """
        Trims the output streams according to ``check`` setting, so that
        they can be compared with :attr:`expected`. For ``begin``, only that
        many first characters are kept as there are in the expected stream;
        for ``end``, that many last characters.

        :param actual: outputs of the tested binary
        :returns: Trimmed outputs, ``actual`` itself, if there are no
            expected values, or the name of an unknown ``check`` value.
        """
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
                    # [-0:] would keep the whole stream
                    streams[ndx] = streams[ndx][-ex_len:] if ex_len else ""
                else:
                    return check
        return ProcessIO(returncode=returncode, stdout=streams[0], stderr=streams[1])

    @staticmethod
    def text_diff(
        header: str, expected: str, actual: str, pre_mark: str = "", post_mark: str = ""
    ):
        """
        Formats a report of differing values, showing both values and their
        unified diff.

        :param header: title of the report
        :param expected: expected value
        :param actual: actual value
        :param pre_mark: text placed before both values, e.g. ``...``
        :param post_mark: text placed after both values, e.g. ``...``
        :returns: Formatted report.
        """
        return f"""{header}
  Expected:
    {pre_mark}{repr(expected)}{post_mark}
  Actual:
    {pre_mark}{repr(actual)}{post_mark}

Diff:
{_diff(expected, actual)}
"""

    def report_io(self, actual: ProcessIO):
        """
        Reports differences between the expected and actual return code and
        output streams. Streams checked with ``begin`` or ``end`` are marked
        with ``...`` on the clipped side.

        :param actual: outputs of the tested binary, already clipped
        :returns: Report of the differences, or an empty string, if there
            are no expected values or nothing differs.
        """
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
        file: FileWrite,
    ):
        """
        Reports differences between the generated and expected file.

        :param file: file pair to report
        :returns: Report with a header naming the file, noting missing or
            binary files, or with the diff of text files.
        """
        header = (
            f"{file.generated.filename} [{'BIN' if file.generated.binary else 'TXT'}]"
        )

        if file.generated.empty:
            header += "\n  New file was not present to be read"
        if file.template.empty:
            header += (
                f"\n  Test file {file.template.filename} was not present to be read"
            )

        if file.generated.empty or file.template.empty:
            return header

        if file.binary:
            return header + "\n  Binary files differ"

        return Test.text_diff(
            header,
            expected=cast(str, file.template.content),
            actual=cast(str, file.generated.content),
        )

    def test_footer(self, env: Env, tempdir: str):
        """
        Formats the information needed to re-run a failed test: the command
        line, prefixed with the environment variables of the test (and the
        ones starting with :attr:`Env.reportable_env_prefix
        <proj_flow.ext.test_runner.driver.env.Env.reportable_env_prefix>`),
        the working directory and the test file.

        :param env: environment of the test run
        :param tempdir: value for ``$TMP``
        :returns: Multiline footer text.
        """
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
        """
        Clears the expected values of the test and stores the test file, so
        the next run can record new values.

        :param lang: new language for the test, if not ``None``
        """
        if lang is not None:
            self.lang = lang
            self.data["lang"] = lang
        self.expected = None
        self.data["expected"] = None
        self.store()

    def store(self):
        """
        Writes :attr:`data` back to the test file as YAML.
        """
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
        """
        Resolves a path against the working directory of the test.

        :param filename: path relative to the working directory of the test
        :returns: Path joined with :attr:`cwd`.
        """
        return os.path.join(self.cwd, filename)

    def chdir(self, sub):
        """
        Changes the working directory of the test. For a ``linear`` test,
        changes the working directory of the current process as well.

        :param sub: path relative to the current working directory of the test
        """
        self.cwd = os.path.abspath(os.path.join(self.cwd, sub))
        if self.linear:
            os.chdir(self.cwd)

    def ls(self, sub):
        """
        Prints names of the entries of a directory, sorted case-insensitively,
        with ``/`` appended to subdirectories.

        :param sub: path relative to the working directory of the test
        """
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
        """
        Removes a directory with all its contents.

        :param sub: path relative to the working directory of the test
        """
        shutil.rmtree(self.path(sub))

    def cp(self, src: str, dst: str):
        """
        Copies a file, together with its metadata.

        :param src: source path, relative to the working directory of the test
        :param dst: destination path, relative to the working directory of the
            test
        """
        shutil.copy2(self.path(src), self.path(dst))

    def makedirs(self, sub):
        """
        Creates a directory with all missing parents.

        :param sub: path relative to the working directory of the test
        """
        os.makedirs(self.path(sub), exist_ok=True)

    def store_output(self, name: str, args: list[str]):
        """
        Runs a command and stores its stripped standard output as a variable,
        which can later be used as ``$name`` in the arguments of the test. If
        the command is the name of the tested binary, it is replaced with the
        path to that binary.

        :param name: name of the variable
        :param args: command line to run
        """
        env = self.current_env

        if env is not None and args[0] == env.target_name:
            args[0] = env.target

        proc = subprocess.run(args, shell=False, capture_output=True, cwd=self.cwd)
        self.additional_env[name] = proc.stdout.decode("UTF-8").strip()
        print(f"export {name}={self.additional_env[name]}")

    @staticmethod
    def load(filename: Path, count: int):
        """
        Loads a test from a JSON or YAML file.

        :param filename: path to the test file
        :param count: position of the test in the test suite
        :returns: Loaded test.
        """
        contents = filename.read_text(encoding="UTF-8")
        tree = cast(dict, yaml.load(contents, Loader=Loader))
        return Test(tree, filename, count)
