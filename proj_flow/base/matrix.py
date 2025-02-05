# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.base.matrix** operates on lists of
:class:`run configurations <proj_flow.api.env.Config>`. It provides means to
build cartesian products for multiple sets, to load the GitHub Actions Job
strategy matrix from a set of YAML files, or to put additional filters on the
resulting set of configurations.
"""

import os
import sys
from typing import Dict, Iterable, List, Tuple, TypeVar

import yaml

T = TypeVar("T")


def find_compiler(
    compiler: str, config_names: Dict[str, List[str]]
) -> Tuple[str, List[str]]:
    """
    Locates the C and C++ names of compilers corresponding to the current
    compiler.

    :param compiler: Name ofthe compiuler to map, taken from the ``"compiler"``
        entry in run :class:`config<proj_flow.api.env.Config>`.
    :param config_names: Dictionary of mapping from compiler name to C/C++
        names, taken from ``"compiler.names"`` entry in flow config file.
    """
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


def flatten(array: Iterable[List[T]]) -> List[T]:
    """
    Turns list of lists into a list.

    :param array: List of lists to flatten
    :returns: a list with all items expanded
    """
    return [item for sublist in array for item in sublist]


def matches(tested: dict, test: dict) -> bool:
    """
    Checks, if the tested dictionary contains all the values from test
    dictionary.

    :param tested: Dictionary to check
    :param test: Dictionary to check against

    :returns: `True`, if all keys from `test` are in `tested` and have the same
        values, `False` otherwise.
    """

    for key, value in test.items():
        val = tested.get(key)
        if val != value:
            return False
    return True


def matches_any(tested: dict, tests: List[dict]):
    """
    Checks, if the tested dictionary contains all the values from at least one
    of test dictionaries.

    :param tested: Dictionary to check
    :param tests: List of dictionaries to check against

    :returns: `True`, if at least one test :func:`matches` `tested`
        dictionary, `False` otherwise.
    """

    for test in tests:
        if matches(tested, test):
            return True
    return False


def cartesian(input: Dict[str, list]) -> List[dict]:
    """
    Calculates the cartesian product of all axes in `input`.

    The input dictionary is source of all axes this product is calculated from.
    The key to the dictionary names the set and value under each key represents
    the set to be multiplied.

    The output list contains each possible dictionary, where key set is
    identical to the input key set and each value is one of the values in the
    input axis.

    :param input: A dictionary with each axis and its values
    :returns: A list of all possible permutation of axes values; order in which
        each permutation appears in resulting list is not guaranteed.

    Example:
    --------

    .. code-block:: python
        :caption: Input

        {
            "key-1": ["value-1", "value-2"],
            "key-2": [True, False],
            "key-3": [1, 2, 3],
        }

    .. code-block:: python
        :caption: Possible output

        [
            { "key-1": "value-1", "key-2": [True], "key-3": 1 },
            { "key-1": "value-1", "key-2": [True], "key-3": 2 },
            { "key-1": "value-1", "key-2": [True], "key-3": 3 },
            { "key-1": "value-1", "key-2": [False], "key-3":  1 },
            { "key-1": "value-1", "key-2": [False], "key-3":  2 },
            { "key-1": "value-1", "key-2": [False], "key-3":  3 },
            { "key-1": "value-2", "key-2": [True], "key-3":  1 },
            { "key-1": "value-2", "key-2": [True], "key-3":  2 },
            { "key-1": "value-2", "key-2": [True], "key-3":  3 },
            { "key-1": "value-2", "key-2": [False], "key-3":  1 },
            { "key-1": "value-2", "key-2": [False], "key-3":  2 },
            { "key-1": "value-2", "key-2": [False], "key-3":  3 },
        ]
    """
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
    """
    Loads config definitions from files under `matrix_paths` to produce
    cartesian product of the matrix, expanded and/or contracted according to
    rules used by GitHub Action workflow `strategies`_. Please note when
    comparing to GitHub documentation:

    - only scalar values are supported in the ``matrix`` dictionary.
    - only ``matrix``, ``include`` and ``exclude`` keys are allowed.

    :param matrix_paths: The list of filenames pointing to YAML files with
        ``matrix``, ``include`` and ``exclude`` entries.
    :returns: A tuple of cartesian product for the config matrix, with
        inclusions and exclusions as described in GitHub docs and a list of key
        names in the ``matrix`` dictionary.

    .. _strategies: https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions#jobsjob_idstrategy
    """
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
