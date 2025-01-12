# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)


import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, cast

from .matrix import cartesian, find_compiler, flatten, load_matrix, matches_any
from .uname import uname

platform = uname()[0]


def _compiler_inner(
    value: str, used_compilers: Dict[str, List[str]], config_names: Dict[str, List[str]]
):
    compiler, names = find_compiler(value, config_names)
    if compiler not in used_compilers:
        used_compilers[compiler] = []
    used_compilers[compiler].append(names)
    return compiler


def _compiler(used_compilers: Dict[str, List[str]], config_names: Dict[str, List[str]]):
    return lambda value: _compiler_inner(value, used_compilers, config_names)


def _boolean_inner(value: str, with_name: str):
    v = value.lower()
    return v in _TRUE or v == with_name


def _boolean(with_name: str):
    return lambda value: _boolean_inner(value, with_name)


_TRUE = {"true", "on", "yes", "1"}
boolean_sanitizer = _boolean("with-sanitizer")


def _types(used_compilers: Dict[str, List[str]], config_names: Dict[str, List[str]]):
    return {
        "compiler": _compiler(used_compilers, config_names),
        "sanitizer": boolean_sanitizer,
    }


def _config(config: List[str], only_host: bool, types: Dict[str, callable]):
    args = {}
    for arg in config:
        if arg[:1] == "-":
            continue
        _arg = arg.split("=", 1)
        if len(_arg) == 1:
            continue

        name, vals = _arg
        name = name.strip()
        conv = types.get(name, lambda value: value)
        values = {conv(val.strip()) for val in vals.split(",")}
        if name in args:
            values.update(args[name])
        args[name] = list(values)

    if only_host and "os" not in args:
        args["os"] = [platform]

    return args


def _expand_one(config: dict, github_os: str, os_in_name: str):
    os_ver = github_os.split("-")[1]
    build_name = f"{config['build_type']} with {config['compiler']} on {os_in_name}"
    if config["sanitizer"]:
        build_name += " (and sanitizer)"
    config["github_os"] = github_os
    config["build_name"] = build_name
    config["needs_gcc_ppa"] = (
        os_ver != "latest"
        and config["os"] == "ubuntu"
        and int(os_ver.split(".")[0]) < 24
    )
    return config


def _expand_config(config: dict, spread_lts: bool, lts_list: Dict[str, List[str]]):
    if spread_lts:
        spread = lts_list.get(config["os"], [])
        if len(spread):
            return [
                _expand_one({key: config[key] for key in config}, lts, lts)
                for lts in spread
            ]
    return [_expand_one(config, f"{config['os']}-latest", config["os"])]


_flow_config_default_compiler: Optional[Dict[str, str]] = None


def default_compiler():
    try:
        return os.environ["DEV_CXX"]
    except KeyError:
        pass

    try:
        return _flow_config_default_compiler[platform]
    except KeyError:
        print(f"KeyError: {platform} in {_flow_config_default_compiler}")
        return "?"
    except TypeError:
        print(f"TypeError: internal: flow config not ready yet")
        return "?"


def _load_flow_data(rt: "Runtime"):
    root = ".flow"
    paths = [os.path.join(root, "matrix.json")]
    if rt.official:
        paths.append(os.path.join(root, "official.json"))
    matrix, keys = load_matrix(*paths)

    if rt.no_coverage:
        for conf in matrix:
            if "coverage" in conf:
                del conf["coverage"]

    return matrix, keys


def _hide(arg: str, secrets: List[str]):
    for secret in secrets:
        arg = arg.replace(secret, "?" * max(15, len(secret)))
    return arg


def _print_arg(arg: str, secrets: List[str]):
    color = ""
    arg = _hide(arg, secrets)
    if arg[:1] == "-":
        color = "\033[2;37m"
    arg = shlex.join([arg])
    if color == "" and arg[:1] in ["'", '"']:
        color = "\033[2;34m"
    if color == "":
        return arg
    return f"{color}{arg}\033[m"


def _print_cmd(*args: str, use_color: bool = True, secrets: List[str]):
    if not use_color:
        cmd = shlex.join([args[0]])
        print(cmd, shlex.join(_hide(arg) for arg in args[1:]))
        return

    cmd = shlex.join([args[0]])
    args = " ".join([_print_arg(arg, secrets) for arg in args[1:]])
    print(f"\033[33m{cmd}\033[m {args}", file=sys.stderr)


@dataclass
class RunAlias:
    name: str
    doc: str
    steps: List[str]

    @staticmethod
    def from_json(name: str, alias: dict):
        doc: str = alias.get("doc", "")
        steps: List[str] = alias.get("steps", [])
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
                os.path.join(".flow", "config.json"),
                encoding="UTF-8",
            ) as f:
                self._cfg = json.load(f)
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
    def compiler_names(self) -> Dict[str, List[str]]:
        return self.compiler.get("names", {})

    @property
    def shortcuts(self) -> Dict[str, dict]:
        return self._cfg.get("shortcuts", {})


class Runtime(FlowConfig):
    dry_run: bool
    silent: bool
    official: bool
    no_coverage: bool
    use_color: bool
    platform: str
    secrets: List[str] = []

    def __init__(self, args: argparse.Namespace):
        super().__init__()

        self.dry_run = args.dry_run
        self.silent = args.silent
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

    @property
    def only_host(self):
        return not (self.dry_run or self.official)

    def cmd(self, *args: str):
        if not self.silent:
            _print_cmd(*args, use_color=self.use_color, secrets=self.secrets)
        if not self.dry_run:
            result = subprocess.run(args)
            if result.returncode != 0:
                print(
                    f"cxx-flow: error: {args[0]} ended in failure, exiting",
                    file=sys.stderr,
                )
                sys.exit(1)


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
    def build_type(self) -> str:
        return self.items.get("build_type", "")

    @property
    def build_name(self) -> str:
        return self.items.get("build_name", "")

    @property
    def preset(self) -> str:
        return self.items.get("preset", "")

    @property
    def build_generator(self) -> str:
        return self.items.get("build_generator", "")


class Configs:
    usable: List[Config] = []

    def __init__(self, args: argparse.Namespace):
        super()
        rt = Runtime(args)
        matrix, keys = _load_flow_data(rt)

        used_compilers: Dict[str, List[str]] = {}

        types = _types(used_compilers=used_compilers, config_names=rt.compiler_names)
        arg_configs = cartesian(_config(flatten(args.configs), rt.only_host, types))

        # from commands/github
        spread_lts = hasattr(args, "matrix") and not not args.matrix

        turned = flatten(
            [
                _expand_config(config, spread_lts, rt.lts_list)
                for config in matrix
                if len(arg_configs) == 0 or matches_any(config, arg_configs)
            ]
        )

        postproc_exclude = rt.postproc_exclude
        usable = [
            config
            for config in turned
            if len(postproc_exclude) == 0 or not matches_any(config, postproc_exclude)
        ]

        self.usable = []
        for conf in usable:
            try:
                compilers = used_compilers[conf["compiler"]]
            except KeyError:
                fallback_compiler = find_compiler(
                    conf["compiler"], config_names=rt.compiler_names
                )
                compilers = [fallback_compiler[1]]
            for compiler in compilers:
                self.usable.append(
                    Config(
                        {
                            **conf,
                            "compiler": compiler,
                            "--orig-compiler": conf["compiler"],
                        },
                        keys,
                    )
                )
