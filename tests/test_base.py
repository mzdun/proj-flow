"""Tests for the small helpers in ``proj_flow.base``."""

import sys
import textwrap

import pytest

from proj_flow.base import matrix
from proj_flow.base.name_list import name_list


@pytest.mark.parametrize(
    "names, expected",
    [
        ([], ""),
        (["a"], "a"),
        (["a", "b"], "a and b"),
        (["a", "b", "c"], "a, b and c"),
    ],
)
def test_name_list(names, expected):
    assert name_list(names) == expected


def test_flatten():
    assert matrix.flatten([[1, 2], [], [3]]) == [1, 2, 3]


def test_matches():
    tested = {"os": "ubuntu", "build_type": "Debug", "sanitizer": True}
    assert matrix.matches(tested, {})
    assert matrix.matches(tested, {"os": "ubuntu"})
    assert matrix.matches(tested, {"os": "ubuntu", "sanitizer": True})
    assert not matrix.matches(tested, {"os": "windows"})
    assert not matrix.matches(tested, {"compiler": "gcc"})


def test_partially_matches():
    tested = {"os": "ubuntu", "build_type": "Debug"}
    assert matrix.partially_matches(tested, {"os": "ubuntu", "compiler": "gcc"})
    assert not matrix.partially_matches(tested, {"os": "windows"})
    # no shared keys at all is not a match
    assert not matrix.partially_matches(tested, {"compiler": "gcc"})
    assert not matrix.partially_matches(tested, {})


def test_matches_any():
    tested = {"os": "ubuntu"}
    assert matrix.matches_any(tested, [{"os": "windows"}, {"os": "ubuntu"}])
    assert not matrix.matches_any(tested, [{"os": "windows"}])
    assert not matrix.matches_any(tested, [])


def test_cartesian():
    product = matrix.cartesian({"a": [1, 2], "b": ["x", "y", "z"]})
    assert len(product) == 6
    expected = [{"a": a, "b": b} for a in [1, 2] for b in ["x", "y", "z"]]
    assert sorted(product, key=repr) == sorted(expected, key=repr)


def test_cartesian_empty():
    assert matrix.cartesian({}) == [{}]
    assert matrix.cartesian({"a": []}) == []


@pytest.mark.parametrize(
    "compiler, names, expected",
    [
        ("gcc", {"gcc": ["gcc", "g++"]}, ("gcc", ["gcc", "g++"])),
        ("gcc-14", {"gcc": ["gcc", "g++"]}, ("gcc", ["gcc-14", "g++-14"])),
        ("stdclang", {}, ("clang", ["stdclang"])),
        ("unknown", {}, ("unknown", ["unknown"])),
    ],
)
def test_find_compiler(compiler, names, expected):
    assert matrix.find_compiler(compiler, names) == expected


@pytest.mark.skipif(sys.platform != "win32", reason="extension stripped on Windows")
def test_find_compiler_strips_exe_on_windows():
    assert matrix.find_compiler("cl.exe", {"cl": ["cl", "cl"]}) == ("cl", ["cl", "cl"])


def _write(path, text):
    path.write_text(textwrap.dedent(text), encoding="UTF-8")
    return str(path)


def test_load_matrix_missing_files(tmp_path):
    assert matrix.load_matrix(str(tmp_path / "missing.yml")) == ([], [])


def test_load_matrix_include_exclude(tmp_path):
    main = _write(
        tmp_path / "matrix.yml",
        """
        matrix:
          os: [ubuntu, windows]
          build_type: [Debug, Release]
        include:
          - os: ubuntu
            compiler: gcc
          - os: windows
            compiler: msvc
        exclude:
          - os: windows
            build_type: Debug
        """,
    )

    configs, keys = matrix.load_matrix(main)

    assert keys == ["os", "build_type"]
    assert len(configs) == 3
    assert {"os": "windows", "build_type": "Release", "compiler": "msvc"} in configs
    assert all(
        not (c["os"] == "windows" and c["build_type"] == "Debug") for c in configs
    )
    assert all(c["compiler"] == "gcc" for c in configs if c["os"] == "ubuntu")


def test_load_matrix_merges_additional_files(tmp_path):
    main = _write(
        tmp_path / "matrix.yml",
        """
        matrix:
          os: [ubuntu]
          sanitizer: [false]
        exclude: []
        """,
    )
    extra = _write(
        tmp_path / "extra.yml",
        """
        matrix:
          os: [macos]
          sanitizer: true
          new_axis: [1]
        exclude:
          - os: macos
        """,
    )

    configs, keys = matrix.load_matrix(main, extra)

    assert keys == ["os", "sanitizer", "new_axis"]
    expected = [
        {"os": "ubuntu", "sanitizer": False, "new_axis": 1},
        {"os": "ubuntu", "sanitizer": True, "new_axis": 1},
    ]
    assert sorted(configs, key=repr) == sorted(expected, key=repr)


@pytest.mark.parametrize("first_extra", ["", "exclude:\n", "exclude: []\n"])
def test_load_matrix_merges_exclude_into_file_without_one(tmp_path, first_extra):
    main = _write(tmp_path / "matrix.yml", f"matrix:\n  os: [ubuntu]\n{first_extra}")
    extra = _write(
        tmp_path / "extra.yml",
        "matrix:\n  os: [macos]\nexclude:\n  - os: macos\n",
    )

    configs, _ = matrix.load_matrix(main, extra)

    assert configs == [{"os": "ubuntu"}]


@pytest.mark.parametrize("first_extra", ["", "include:\n"])
def test_load_matrix_merges_include_into_file_without_one(tmp_path, first_extra):
    main = _write(tmp_path / "matrix.yml", f"matrix:\n  os: [ubuntu]\n{first_extra}")
    extra = _write(
        tmp_path / "extra.yml",
        "include:\n  - os: ubuntu\n    compiler: gcc\n",
    )

    configs, _ = matrix.load_matrix(main, extra)

    assert configs == [{"os": "ubuntu", "compiler": "gcc"}]


@pytest.mark.parametrize("first", ["exclude: []\n", "matrix:\nexclude: []\n"])
def test_load_matrix_merges_matrix_into_file_without_one(tmp_path, first):
    main = _write(tmp_path / "matrix.yml", first)
    extra = _write(tmp_path / "extra.yml", "matrix:\n  os: [ubuntu, macos]\n")

    configs, keys = matrix.load_matrix(main, extra)

    assert keys == ["os"]
    assert sorted(configs, key=repr) == [{"os": "macos"}, {"os": "ubuntu"}]
