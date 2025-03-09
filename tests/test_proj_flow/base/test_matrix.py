# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from proj_flow.base import matrix

from ..mocks import fs

COMPILERS = {"clang": ["clang", "clang++"], "gcc": ["gcc", "g++"]}


def test_find_compiler():
    compiler, compilers = matrix.find_compiler("clang", COMPILERS)
    assert compiler == "clang"
    assert compilers == ["clang", "clang++"]

    compiler, compilers = matrix.find_compiler("gcc-2024", COMPILERS)
    assert compiler == "gcc"
    assert compilers == ["gcc-2024", "g++-2024"]

    compiler, compilers = matrix.find_compiler("/usr/bin/gcc", COMPILERS)
    assert compiler == "gcc"
    assert compilers == ["/usr/bin/gcc", "/usr/bin/g++"]

    compiler, compilers = matrix.find_compiler("msvc", COMPILERS)
    assert compiler == "msvc"
    assert compilers == ["msvc"]

    compiler, compilers = matrix.find_compiler("stdclang", COMPILERS)
    assert compiler == "clang"
    assert compilers == ["stdclang"]


def test_flatten():
    assert matrix.flatten(
        [["a", "b", "c", "d", "e"], ["i", "ii", "iv", "v"], ["9"]]
    ) == ["a", "b", "c", "d", "e", "i", "ii", "iv", "v", "9"]


def test_small_matrix(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "matrix.json": {
                    "matrix": {
                        "key-1": ["value-1", "value-2"],
                        "key-2": [True, False],
                        "key-3": [1, 2, 3],
                    }
                }
            }
        ),
    )

    expanded, keys = matrix.load_matrix("matrix.json")

    assert expanded == [
        {"key-1": "value-1", "key-2": True, "key-3": 1},
        {"key-1": "value-2", "key-2": True, "key-3": 1},
        {"key-1": "value-1", "key-2": False, "key-3": 1},
        {"key-1": "value-2", "key-2": False, "key-3": 1},
        {"key-1": "value-1", "key-2": True, "key-3": 2},
        {"key-1": "value-2", "key-2": True, "key-3": 2},
        {"key-1": "value-1", "key-2": False, "key-3": 2},
        {"key-1": "value-2", "key-2": False, "key-3": 2},
        {"key-1": "value-1", "key-2": True, "key-3": 3},
        {"key-1": "value-2", "key-2": True, "key-3": 3},
        {"key-1": "value-1", "key-2": False, "key-3": 3},
        {"key-1": "value-2", "key-2": False, "key-3": 3},
    ]

    assert keys == ["key-1", "key-2", "key-3"]


def test_matrix_not_found(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "matrix.json": {
                    "matrix": {
                        "key-1": ["value-1", "value-2"],
                        "key-2": [True, False],
                        "key-3": [1, 2, 3],
                    }
                }
            }
        ),
    )

    expanded, keys = matrix.load_matrix("missing-matrix.json")

    assert expanded == []
    assert not keys


def test_matrix_exclude(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "matrix.json": {
                    "matrix": {
                        "key-1": ["value-1", "value-2"],
                        "key-2": [True, False],
                        "key-3": [1, 2, 3],
                    },
                    "exclude": [{"key-1": "value-2", "key-2": False}],
                }
            }
        ),
    )

    expanded, keys = matrix.load_matrix("matrix.json")

    assert expanded == [
        {"key-1": "value-1", "key-2": True, "key-3": 1},
        {"key-1": "value-2", "key-2": True, "key-3": 1},
        {"key-1": "value-1", "key-2": False, "key-3": 1},
        {"key-1": "value-1", "key-2": True, "key-3": 2},
        {"key-1": "value-2", "key-2": True, "key-3": 2},
        {"key-1": "value-1", "key-2": False, "key-3": 2},
        {"key-1": "value-1", "key-2": True, "key-3": 3},
        {"key-1": "value-2", "key-2": True, "key-3": 3},
        {"key-1": "value-1", "key-2": False, "key-3": 3},
    ]

    assert keys == ["key-1", "key-2", "key-3"]


def test_matrix_include(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "matrix.json": {
                    "matrix": {
                        "key-1": ["value-1", "value-2"],
                        "key-2": [True, False],
                        "key-3": [1, 2, 3],
                    },
                    "exclude": [{"key-1": "value-2", "key-2": False}],
                    "include": [{"key-1": "value-2", "option": "plugin"}],
                }
            }
        ),
    )

    expanded, keys = matrix.load_matrix("matrix.json")

    assert expanded == [
        {"key-1": "value-1", "key-2": True, "key-3": 1},
        {"key-1": "value-2", "key-2": True, "key-3": 1, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 1},
        {"key-1": "value-1", "key-2": True, "key-3": 2},
        {"key-1": "value-2", "key-2": True, "key-3": 2, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 2},
        {"key-1": "value-1", "key-2": True, "key-3": 3},
        {"key-1": "value-2", "key-2": True, "key-3": 3, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 3},
    ]

    assert keys == ["key-1", "key-2", "key-3"]


def test_matrix_in_another_castle(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "this-castle.json": {},
                "princess-peach.json": {
                    "matrix": {
                        "key-1": ["value-1", "value-2"],
                        "key-2": [True, False],
                        "key-3": [1, 2, 3],
                    },
                    "exclude": [{"key-1": "value-2", "key-2": False}],
                    "include": [{"key-1": "value-2", "option": "yahoo!"}],
                },
            }
        ),
    )

    expanded, keys = matrix.load_matrix("this-castle.json", "princess-peach.json")

    assert expanded == [
        {"key-1": "value-1", "key-2": True, "key-3": 1},
        {"key-1": "value-2", "key-2": True, "key-3": 1, "option": "yahoo!"},
        {"key-1": "value-1", "key-2": False, "key-3": 1},
        {"key-1": "value-1", "key-2": True, "key-3": 2},
        {"key-1": "value-2", "key-2": True, "key-3": 2, "option": "yahoo!"},
        {"key-1": "value-1", "key-2": False, "key-3": 2},
        {"key-1": "value-1", "key-2": True, "key-3": 3},
        {"key-1": "value-2", "key-2": True, "key-3": 3, "option": "yahoo!"},
        {"key-1": "value-1", "key-2": False, "key-3": 3},
    ]

    assert keys == ["key-1", "key-2", "key-3"]


def test_matrix_split(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "matrix.json": {
                    "matrix": {
                        "key-1": ["value-1", "value-2"],
                    },
                    "exclude": [{"key-1": "value-2", "key-2": False}],
                    "include": [{"key-1": "value-2", "option": "plugin"}],
                },
                "additional.json": {
                    "matrix": {
                        "key-2": [True, False],
                        "key-3": [1, 2, 3],
                    },
                    "include": [{"key-1": "value-2", "option": "plugin"}],
                },
            }
        ),
    )

    expanded, keys = matrix.load_matrix("matrix.json", "additional.json")

    assert expanded == [
        {"key-1": "value-1", "key-2": True, "key-3": 1},
        {"key-1": "value-2", "key-2": True, "key-3": 1, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 1},
        {"key-1": "value-1", "key-2": True, "key-3": 2},
        {"key-1": "value-2", "key-2": True, "key-3": 2, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 2},
        {"key-1": "value-1", "key-2": True, "key-3": 3},
        {"key-1": "value-2", "key-2": True, "key-3": 3, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 3},
    ]

    assert keys == ["key-1", "key-2", "key-3"]


def test_matrix_split_2(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "matrix.json": {
                    "matrix": {
                        "key-1": ["value-1", "value-2"],
                        "key-2": [True, False],
                        "key-3": [1, 2],
                    },
                    "exclude": [{"key-1": "value-2", "key-2": False}],
                    "include": [{"key-1": "value-2", "option": "plugin"}],
                },
                "additional.json": {
                    "matrix": {
                        "key-3": [2, 3],
                    },
                    "include": [{"key-1": "value-2", "option": "plugin"}],
                },
            }
        ),
    )

    expanded, keys = matrix.load_matrix("matrix.json", "additional.json")

    assert expanded == [
        {"key-1": "value-1", "key-2": True, "key-3": 1},
        {"key-1": "value-2", "key-2": True, "key-3": 1, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 1},
        {"key-1": "value-1", "key-2": True, "key-3": 2},
        {"key-1": "value-2", "key-2": True, "key-3": 2, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 2},
        {"key-1": "value-1", "key-2": True, "key-3": 3},
        {"key-1": "value-2", "key-2": True, "key-3": 3, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 3},
    ]

    assert keys == ["key-1", "key-2", "key-3"]


def test_matrix_split_3a(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "matrix.json": {
                    "matrix": {
                        "key-1": ["value-1", "value-2"],
                        "key-2": [True, False],
                        "key-3": [1, 2, 3],
                    },
                    "exclude": [{"key-1": "value-2", "key-2": False}],
                    "include": [{"key-1": "value-2", "option": "plugin"}],
                },
                "additional.json": {
                    "matrix": {"key-3": 3},
                },
            }
        ),
    )

    expanded, keys = matrix.load_matrix("matrix.json", "additional.json")

    assert expanded == [
        {"key-1": "value-1", "key-2": True, "key-3": 1},
        {"key-1": "value-2", "key-2": True, "key-3": 1, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 1},
        {"key-1": "value-1", "key-2": True, "key-3": 2},
        {"key-1": "value-2", "key-2": True, "key-3": 2, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 2},
        {"key-1": "value-1", "key-2": True, "key-3": 3},
        {"key-1": "value-2", "key-2": True, "key-3": 3, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 3},
    ]

    assert keys == ["key-1", "key-2", "key-3"]


def test_matrix_split_3b(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "matrix.json": {
                    "matrix": {
                        "key-1": ["value-1", "value-2"],
                        "key-2": [True, False],
                        "key-3": [1, 2],
                    },
                    "exclude": [{"key-1": "value-2", "key-2": False}],
                    "include": [{"key-1": "value-2", "option": "plugin"}],
                },
                "additional.json": {
                    "matrix": {"key-3": 3},
                },
            }
        ),
    )

    expanded, keys = matrix.load_matrix("matrix.json", "additional.json")

    assert expanded == [
        {"key-1": "value-1", "key-2": True, "key-3": 1},
        {"key-1": "value-2", "key-2": True, "key-3": 1, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 1},
        {"key-1": "value-1", "key-2": True, "key-3": 2},
        {"key-1": "value-2", "key-2": True, "key-3": 2, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 2},
        {"key-1": "value-1", "key-2": True, "key-3": 3},
        {"key-1": "value-2", "key-2": True, "key-3": 3, "option": "plugin"},
        {"key-1": "value-1", "key-2": False, "key-3": 3},
    ]

    assert keys == ["key-1", "key-2", "key-3"]
