"""Tests for the ``sanitizer`` matrix key: booleans and named sanitizers."""

import textwrap
from types import SimpleNamespace

import pytest

from proj_flow.api import env
from proj_flow.base import matrix
from proj_flow.flow.cmake_vars import cmake_value
from proj_flow.flow import configs


@pytest.mark.parametrize(
    "value, expected",
    [
        ("true", True),
        ("ON", True),
        ("with-sanitizer", True),
        ("off", False),
        ("0", False),
        ("without-sanitizer", False),
        ("thread", "thread"),
        ("Address", "address"),
    ],
)
def test_sanitizer_values(value, expected):
    assert configs._sanitizer(value) == expected


def _filter(matrix_yml: str, tmp_path, *args: str):
    path = tmp_path / "matrix.yml"
    path.write_text(textwrap.dedent(matrix_yml), encoding="UTF-8")
    loaded, _ = matrix.load_matrix(str(path))
    types = {"sanitizer": configs._sanitizer}
    wanted = matrix.cartesian(configs._config(list(args), False, types))
    return [conf for conf in loaded if not wanted or matrix.matches_any(conf, wanted)]


NAMED = """
    matrix:
      build_type: [Debug]
      sanitizer: [address, thread, off]
"""

BOOLEAN = """
    matrix:
      build_type: [Debug]
      sanitizer: [true, false]
"""


@pytest.mark.parametrize(
    "matrix_yml, arg, expected",
    [
        (NAMED, "sanitizer=thread", ["thread"]),
        (NAMED, "sanitizer=address,thread", ["address", "thread"]),
        (NAMED, "sanitizer=off", [False]),
        (NAMED, "sanitizer=on", []),
        (BOOLEAN, "sanitizer=with-sanitizer", [True]),
        (BOOLEAN, "sanitizer=no", [False]),
        (BOOLEAN, "sanitizer=thread", []),
    ],
)
def test_filtering(matrix_yml, arg, expected, tmp_path):
    found = _filter(matrix_yml, tmp_path, arg)
    assert sorted(conf["sanitizer"] for conf in found) == sorted(
        expected, key=lambda value: (str(type(value)), value)
    )


@pytest.mark.parametrize(
    "sanitizer, suffix",
    [
        (False, ""),
        (True, " (and sanitizer)"),
        ("thread", " (and thread sanitizer)"),
    ],
)
def test_build_name(sanitizer, suffix):
    config = {
        "build_type": "Debug",
        "compiler": "gcc",
        "os": "ubuntu",
        "sanitizer": sanitizer,
    }
    expanded = configs._expand_one(config, "ubuntu-24.04", "ubuntu-24.04")
    assert expanded["build_name"] == f"Debug with gcc on ubuntu-24.04{suffix}"


RT = SimpleNamespace(cutdown_os=True, missing=None)


@pytest.mark.parametrize(
    "reference, sanitizer, expected",
    [
        ("?config:sanitizer", True, "ON"),
        ("?config:sanitizer", False, "OFF"),
        ("?config:sanitizer", "thread", "ON"),
        ("?config:sanitizer=thread", "thread", "ON"),
        ("?config:sanitizer=thread", "address", "OFF"),
        ("?config:sanitizer=thread", False, "OFF"),
        ("?config:sanitizer=thread", True, "OFF"),
        ("?config:sanitizer=true", True, "ON"),
        ("?config:sanitizer=false", False, "ON"),
        ("?config:unknown=thread", "thread", "OFF"),
        ("?runtime:cutdown_os", False, "ON"),
        ("?runtime:missing", False, "OFF"),
        ("config:sanitizer", "thread", "thread"),
        ("literal", False, "literal"),
    ],
)
def test_cmake_value(reference, sanitizer, expected):
    config = env.Config({"sanitizer": sanitizer}, ["sanitizer"])
    assert cmake_value(reference, config, RT) == expected  # type: ignore[arg-type]
