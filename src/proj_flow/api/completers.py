# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.api.completers** defines :py:mod:`argcomplete` functions for
``-C``, ``--step`` and ``-D``.
"""

import os
from typing import Any, Dict, List, Union, cast

import yaml

from proj_flow import api


def cd_completer(prefix, **kwargs):
    target_dir = os.path.dirname(prefix)
    incomplete_part = os.path.basename(prefix)
    try:
        names = os.listdir(target_dir or ".")
    except Exception:
        return  # empty iterator

    for name in names:
        if not name.startswith(incomplete_part):
            continue
        full = os.path.join(target_dir, name)
        if not os.path.isdir(full):
            continue

        yield f"{full}{os.sep}"


def step_completer(prefix: str, parser, **kwargs):
    flow_cfg = cast(api.env.FlowConfig, parser.flow)

    comma_sep = prefix.split(",")
    start = ",".join(comma_sep[:-1])
    if len(comma_sep) > 1:
        start += ","

    current = comma_sep[-1].lower()
    for step in flow_cfg.steps:
        name = cast(str, step.name)
        if name.lower().startswith(current):
            candidate = current + name[len(current) :]
            yield start + candidate


def _str_arg(arg: Union[bool, str]):
    if isinstance(arg, bool):
        return "ON" if arg else "OFF"
    return str(arg)


def matrix_completer(prefix: str, parser, **kwargs):
    flow_cfg = cast(api.env.FlowConfig, parser.flow)

    matrix_yml = os.path.join(flow_cfg.root, ".flow", "matrix.yml")
    with open(matrix_yml, "r", encoding="UTF-8") as contents:
        data: Dict[str, List[Any]] = yaml.load(contents, Loader=yaml.Loader).get(
            "matrix", {}
        )

    comma_sep = prefix.split(",")
    start = ",".join(comma_sep[:-1])
    if len(comma_sep) > 1:
        start += ","

    current = comma_sep[-1].split("=", 1)

    if len(current) == 1:
        completions: List[str] = []
        for key in data:
            if key.startswith(current[0]):
                completions.append(f"{start}{key}=")
        if len(completions) != 1:
            return completions

        current = completions[0].split("=", 1)

    try:
        args = data[current[0]]
    except KeyError:
        return

    completions: List[str] = []
    for arg in map(_str_arg, args):
        if arg.startswith(current[1]):
            completions.append(f"{start}{current[0]}={arg}")

    return completions
