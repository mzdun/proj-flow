# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.flow.configs** provides :class:`Configs`, which uses
:class:`api.env.FlowConfig` to load the matrix definition and filter it out
using ``-D`` switches.
"""


import argparse
import datetime
import os
import sys
from typing import Any, Callable, Dict, Iterable, List, TypeVar, cast

from proj_flow.api import env
from proj_flow.base import matrix

T = TypeVar("T")


def _compiler_inner(
    value: str,
    used_compilers: Dict[str, List[List[str]]],
    config_names: Dict[str, List[str]],
):
    compiler, names = matrix.find_compiler(value, config_names)
    if compiler not in used_compilers:
        used_compilers[compiler] = []
    used_compilers[compiler].append(names)
    return compiler


def _compiler(
    used_compilers: Dict[str, List[List[str]]], config_names: Dict[str, List[str]]
):
    return lambda value: _compiler_inner(value, used_compilers, config_names)


_TRUE = {"true", "on", "yes", "1"}


def _boolean_inner(value: str, with_name: str):
    v = value.lower()
    return v in _TRUE or v == with_name


def _boolean(with_name: str):
    return lambda value: _boolean_inner(value, with_name)


def _number(value):
    try:
        return int(value)
    except ValueError:
        return None


def _types(
    used_compilers: Dict[str, List[List[str]]],
    config_names: Dict[str, List[str]],
    bool_flags: List[str],
    int_flags: List[str],
):
    result: Dict[str, Callable[[Any], Any]] = {
        "compiler": _compiler(used_compilers, config_names),
    }
    for bool_flag in bool_flags:
        result[bool_flag] = _boolean(f"with-{bool_flag.lower()}")
    for int_flag in int_flags:
        result[int_flag] = _number

    return result


def _config(config: List[str], only_host: bool, types: Dict[str, Callable[[str], Any]]):
    args: Dict[str, List[str]] = {}
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
        args["os"] = [env.platform]

    return args


def _expand_one(config: dict, github_os: str, os_in_name: str):
    os_ver = github_os.split("-")[1]
    build_name = f"{config['build_type']} with {config['compiler']} on {os_in_name}"
    if config.get("sanitizer"):
        build_name += " (and sanitizer)"
    config["github_os"] = github_os
    config["build_name"] = build_name
    config["needs_gcc_ppa"] = os_ver != "latest" and config["os"] == "ubuntu"
    return config


PRINTED_LTS_UBUNTU_WARNING = False


def _ubuntu_lts(today=datetime.date.today(), lts_years=5):
    year = today.year
    for y in range(year - lts_years, year + 1):
        if y % 2 != 0:
            continue
        release = datetime.date(y, 4, 1)
        end_of_life = datetime.date(y + lts_years, 1, 31)
        if release > today or end_of_life < today:
            continue
        yield f"ubuntu-{y % 100}.04"


def _lts_list(config: dict, lts_list: Dict[str, List[str]]):
    os_name = config.get("os", None)
    raw = lts_list.get(os_name)
    if os_name == "ubuntu":
        if raw is not None:
            global PRINTED_LTS_UBUNTU_WARNING
            if not PRINTED_LTS_UBUNTU_WARNING:
                PRINTED_LTS_UBUNTU_WARNING = True
                print(
                    "\033[1;33m-- lts.ubuntu in config.yaml is deprecated; "
                    "please remove it, so it can be calculated based on "
                    "current date\033[m",
                    file=sys.stderr,
                )
        else:
            raw = list(_ubuntu_lts())
    return raw or []


def _expand_config(config: dict, spread_lts: bool, lts_list: Dict[str, List[str]]):
    if spread_lts:
        spread = _lts_list(config, lts_list)
        if len(spread):
            return [
                _expand_one({key: config[key] for key in config}, lts, lts)
                for lts in spread
            ]
    os_name = config.get("os", None)
    if os_name is None:
        return [config]
    return [_expand_one(config, f"{os_name}-latest", os_name)]


def _load_flow_data(rt: env.Runtime):
    root = os.path.join(rt.root, ".flow")
    paths = [os.path.join(root, "matrix.yml")]
    if rt.official:
        paths.append(os.path.join(root, "official.yml"))
    configs, keys = matrix.load_matrix(*paths)

    if rt.no_coverage:
        if "coverage" in keys:
            keys.remove("coverage")

        changed = False
        for conf in configs:
            if "coverage" in conf:
                del conf["coverage"]
                changed = True

        if changed:
            copy: List[dict] = []
            for conf in configs:
                if conf not in copy:
                    copy.append(conf)
            configs = copy

    return configs, keys


def _separate_flags(configs: List[dict], keys: List[str]):
    bool_flags: List[str] = []
    int_flags: List[str] = []
    for key in keys:
        has_bool_values = False
        has_int_values = False

        for cfg in configs:
            value = cfg.get(key)
            has_bool_values = has_bool_values or isinstance(value, bool)
            has_int_values = has_int_values or isinstance(value, int)

        if has_bool_values:
            bool_flags.append(key)
        elif has_int_values:
            int_flags.append(key)

    return bool_flags, int_flags


def _each(cb: Callable[[T], Any], items: Iterable[T]):
    for item in items:
        cb(item)


class Configs:  # pylint: disable=too-few-public-methods
    usable: List[env.Config] = []

    @classmethod
    def from_cli(cls, rt: env.Runtime, args: argparse.Namespace, expand_compilers=True):
        configs = cast(List[str], getattr(args, "configs", []))
        matrix = cast(bool, getattr(args, "matrix", False))
        return cls(
            rt=rt, cfgs=configs, spread_lts=matrix, expand_compilers=expand_compilers
        )

    def __init__(
        self, rt: env.Runtime, cfgs: List[str], spread_lts=False, expand_compilers=True
    ):
        configs, keys = _load_flow_data(rt)

        if not configs and not keys:
            self.usable = [env.Config({}, keys)]
            return

        bools, ints = _separate_flags(configs, keys)

        used_compilers: Dict[str, List[List[str]]] = {}

        types = _types(
            used_compilers=used_compilers,
            config_names=rt.compiler_names,
            bool_flags=bools,
            int_flags=ints,
        )
        arg_configs = matrix.cartesian(_config(cfgs, rt.only_host, types))

        if not spread_lts:
            # allow "run" to see the warning about "lts.ubuntu"
            _each(lambda config: _lts_list(config, rt.lts_list), configs)

        config_list = matrix.flatten(
            [
                _expand_config(config, spread_lts, rt.lts_list)
                for config in configs
                if len(arg_configs) == 0 or matrix.matches_any(config, arg_configs)
            ]
        )

        config_list = [
            config
            for config in config_list
            if not rt.postproc_exclude
            or not matrix.matches_any(config, rt.postproc_exclude)
        ]

        if not expand_compilers:
            self.usable = [env.Config(conf, keys) for conf in config_list]
            return

        self.usable = []
        for conf in config_list:
            try:
                comp = conf["compiler"]
            except KeyError:
                self.usable.append(env.Config(conf, keys))
                continue

            try:
                compilers = used_compilers[comp]
            except KeyError:
                fallback_compiler = matrix.find_compiler(
                    comp, config_names=rt.compiler_names
                )
                compilers = [fallback_compiler[1]]
            for compiler in compilers:
                self.usable.append(
                    env.Config(
                        {
                            **conf,
                            "compiler": compiler,
                            "--orig-compiler": conf["compiler"],
                        },
                        keys,
                    )
                )
