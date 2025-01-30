# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)


import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, cast

import yaml

from cxx_flow.base import uname

platform = uname.uname()[0]


_flow_config_default_compiler: Optional[Dict[str, str]] = None


def default_compiler():
    try:
        return os.environ["DEV_CXX"]
    except KeyError:
        pass

    try:
        return _flow_config_default_compiler[platform]
    except KeyError:
        print(
            f"-- KeyError: {platform} in {_flow_config_default_compiler}",
            file=sys.stderr,
        )
        return "?"
    except TypeError:
        print(f"-- TypeError: internal: flow config not ready yet", file=sys.stderr)
        return "?"


class Printer:
    @staticmethod
    def hide(arg: str, secrets: List[str]):
        for secret in secrets:
            arg = arg.replace(secret, "?" * max(15, len(secret)))
        return arg

    @staticmethod
    def print_arg(arg: str, secrets: List[str], raw: bool):
        color = ""
        arg = Printer.hide(arg, secrets)
        if arg[:1] == "-":
            color = "\033[2;37m"
        if not raw:
            arg = shlex.join([arg])
        if color == "" and arg[:1] in ["'", '"']:
            color = "\033[2;34m"
        if color == "":
            return arg
        return f"{color}{arg}\033[m"

    @staticmethod
    def print_cmd(*args: str, use_color: bool = True, secrets: List[str], raw: bool):
        cmd = args[0] if raw else shlex.join([args[0]])
        if not use_color:
            if raw:
                print(cmd, *(Printer.hide(arg) for arg in args[1:]), file=sys.stderr)
            else:
                print(
                    cmd,
                    shlex.join(Printer.hide(arg) for arg in args[1:]),
                    file=sys.stderr,
                )
            return

        args = " ".join([Printer.print_arg(arg, secrets, raw) for arg in args[1:]])
        print(f"\033[33m{cmd}\033[m {args}", file=sys.stderr)


@dataclass
class RunAlias:
    name: str
    doc: str
    steps: List[str]

    @staticmethod
    def from_json(name: str, alias: Union[dict, list]):
        if isinstance(alias, dict):
            doc: str = alias.get("doc", "")
            steps: List[str] = alias.get("steps", [])
        else:
            doc = ""
            steps = alias
        if not doc:
            doc = f'shortcut for "run -s {",".join(steps)}"'

        return RunAlias(name, doc, steps)


class FlowConfig:
    _cfg: dict
    steps: list = []
    aliases: List[RunAlias] = []

    def __init__(self):
        global _flow_config_default_compiler

        try:
            with open(
                os.path.join(".flow", "config.yml"),
                encoding="UTF-8",
            ) as f:
                self._cfg = yaml.load(f, Loader=yaml.Loader)
        except FileNotFoundError:
            self._cfg = {}

        _flow_config_default_compiler = self.compiler_os_default

    @property
    def entry(self) -> Dict[str, dict]:
        return self._cfg.get("entry", {})

    @property
    def compiler(self) -> Dict[str, dict]:
        return self._cfg.get("compiler", {})

    @property
    def compiler_names(self) -> Dict[str, List[str]]:
        return self.compiler.get("names", {})

    @property
    def compiler_os_default(self) -> Dict[str, str]:
        return self.compiler.get("os-default", {})

    @property
    def lts_list(self) -> Dict[str, List[str]]:
        return self._cfg.get("lts", {})

    @property
    def postproc(self) -> dict:
        return self._cfg.get("postproc", {})

    @property
    def postproc_exclude(self) -> List[dict]:
        return self.postproc.get("exclude", [])

    @property
    def shortcuts(self) -> Dict[str, dict]:
        return self._cfg.get("shortcuts", {})


def _mkdir(dirname: str):
    os.makedirs(dirname, exist_ok=True)


def _ls(dirname: str, shallow=True):
    result = []
    for root, dirnames, filenames in os.walk(dirname):
        if shallow:
            dirnames[:] = []

        result.extend(
            os.path.relpath(os.path.join(root, filename), start=dirname)
            for filename in filenames
        )
    return result


def _cp(src: str, dst: str) -> int:
    try:
        dst = os.path.abspath(dst)
        if os.path.isdir(src):
            _mkdir(dst)
            shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)
        else:
            if not os.path.isdir(dst):
                _mkdir(os.path.dirname(dst))
            shutil.copy(src, dst, follow_symlinks=False)
    except FileNotFoundError as err:
        print(err, file=sys.stderr)
        return 1


class Runtime(FlowConfig):
    dry_run: bool
    silent: bool
    verbose: bool
    official: bool
    no_coverage: bool
    use_color: bool
    only_host: bool
    platform: str
    secrets: List[str] = []

    def __init__(self, argsOrRuntime: Union[argparse.Namespace, "Runtime"]):
        super().__init__()

        if isinstance(argsOrRuntime, argparse.Namespace):
            args = argsOrRuntime
            self.dry_run = args.dry_run
            self.silent = args.silent
            self.verbose = args.verbose
            try:
                self.official = args.official
            except AttributeError:
                self.official = False
            self.use_color = True
            self.no_coverage = False
            self.platform = platform

            if "NO_COVERAGE" in os.environ:
                self.no_coverage = True

            if "RELEASE" in os.environ and "GITHUB_ACTIONS" in os.environ:
                self.official = not not json.loads(os.environ["RELEASE"])

            self.only_host = not (self.dry_run or self.official)
        else:
            rt = argsOrRuntime
            self.dry_run = rt.dry_run
            self.silent = rt.silent
            self.verbose = rt.verbose
            self.official = rt.official
            self.no_coverage = rt.no_coverage
            self.use_color = rt.use_color
            self.only_host = rt.only_host
            self.platform = rt.platform
            self.secrets = [*rt.secrets]

    def message(self, *args: str, **kwargs):
        if not self.verbose:
            return

        print("--", *args, **kwargs, file=sys.stderr)

    def print(self, *args: str, raw=False):
        if not self.silent:
            Printer.print_cmd(
                *args, use_color=self.use_color, secrets=self.secrets, raw=raw
            )

    def cmd(self, *args: str):
        self.print(*args)
        if self.dry_run:
            return 0

        result = subprocess.run(args)
        if result.returncode != 0:
            print(
                f"cxx-flow: error: {args[0]} ended in failure, exiting",
                file=sys.stderr,
            )
            return 1
        return 0

    def mkdirs(self, dirname: str):
        self.print("mkdir", "-p", dirname)

        if self.dry_run:
            return 0

        os.makedirs(dirname, exist_ok=True)
        return 0

    def cp(self, src: str, dst: str, regex: Optional[str] = None):
        args = ["cp"]
        if os.path.isdir(src):
            args.append("-r")
        self.print(*args, src, dst)

        if self.dry_run:
            return 0

        if regex is None:
            return _cp(src, dst)

        files = _ls(src)
        files = (name for name in files if re.match(regex, name))
        for name in files:
            result = _cp(os.path.join(src, name), os.path.join(dst, name))
            if result:
                return result
        return 0


@dataclass
class Config:
    items: dict
    keys: List[str]

    def get_path(self, key: str, val: any = None):
        path = key.split(".")
        ctx = self.items
        for step in path:
            if not isinstance(ctx, dict):
                return val
            child = ctx.get(step)
            if child is None:
                return val
            ctx = child
        return cast(any, ctx)

    @property
    def os(self) -> str:
        return self.items.get("os", "")

    @property
    def build_type(self) -> str:
        return self.items.get("build_type", "")

    @property
    def build_name(self) -> str:
        return self.items.get("build_name", "")

    @property
    def build_dir(self) -> str:
        return os.path.join("build", self.preset)

    @property
    def preset(self) -> str:
        return self.items.get("preset", "")

    @property
    def build_generator(self) -> str:
        return self.items.get("build_generator", "")
