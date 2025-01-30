# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)


import os
import sys
from typing import Dict, List, Tuple, TypeVar

import yaml

T = TypeVar("T")


def find_compiler(
    compiler: str, config_names: Dict[str, List[str]]
) -> Tuple[str, List[str]]:
    dirname = os.path.dirname(compiler)
    filename = os.path.basename(compiler)
    if sys.platform == "win32":
        filename = os.path.splitext(filename)[0]
    chunks = filename.split("-", 1)
    if len(chunks) == 1:
        version = None
    else:
        version = chunks[1]
    filename = chunks[0].lower()

    try:
        compiler_names = config_names[filename]
    except:
        compiler_names = [filename]

    compilers = [
        os.path.join(dirname, name if version is None else f"{name}-{version}")
        for name in compiler_names
    ]

    if filename == "stdclang":
        filename = "clang"

    return filename, compilers


def flatten(array: List[List[T]]) -> List[T]:
    return [item for sublist in array for item in sublist]


def matches(tested: dict, test: dict):
    for key, value in test.items():
        val = tested.get(key)
        if val != value:
            return False
    return True


def matches_any(tested: dict, tests: List[dict]):
    for test in tests:
        if matches(tested, test):
            return True
    return False


def cartesian(input: Dict[str, list]) -> List[dict]:
    product = [{}]

    for key, values in input.items():
        next_level = []
        for value in values:
            for obj in product:
                next_level.append({**obj, key: value})
        product = next_level

    return product


def _split_keys(includes: List[dict], keys: List[str]) -> List[Tuple[dict, dict]]:
    result = []
    for include in includes:
        expand_key = {}
        expand_value = {}
        for key, value in include.items():
            if key in keys:
                expand_key[key] = value
            else:
                expand_value[key] = value
        result.append((expand_key, expand_value))
    return result


def load_matrix(*matrix_paths: str) -> Tuple[List[dict], List[str]]:
    setups: List[dict] = []
    for matrix_path in matrix_paths:
        try:
            with open(matrix_path, encoding="UTF-8") as f:
                setups.append(yaml.load(f, Loader=yaml.Loader))
        except FileNotFoundError:
            pass

    if len(setups) == 0:
        return [], []

    setup = setups[0]
    for additional in setups[1:]:
        src_matrix = setup.get("matrix", {})
        src_exclude = setup.get("exclude", [])
        src_include = setup.get("include", [])

        for key, value in additional.get("matrix", {}).items():
            old = src_matrix.get(key)
            if isinstance(old, list) and isinstance(value, list):
                old.extend(value)
            elif isinstance(old, list):
                old.append(value)
            else:
                src_matrix[key] = value
        src_exclude.extend(additional.get("exclude", []))
        src_include.extend(additional.get("include", []))

    raw = setup.get("matrix", {})
    keys = list(raw.keys())
    full = cartesian(raw)

    includes = _split_keys(setup.get("include", []), keys)
    for obj in full:
        for include_key, include_value in includes:
            if not matches(obj, include_key):
                continue
            for key, value in include_value.items():
                obj[key] = value

    excludes = setup.get("exclude", [])
    matrix = [obj for obj in full if not matches_any(obj, excludes)]

    return matrix, keys
