# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
from dataclasses import dataclass

from proj_flow.api import completers

from ..mocks import fs


def _listdir(dirname: str):
    if dirname == "dir-not-found":
        raise FileNotFoundError()
    return [
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
    ]


def _isdir(dirname: str):
    return dirname != f"sub{os.sep}four"


def test_cd(mocker):
    mocker.patch("os.listdir", wraps=_listdir)
    mocker.patch("os.path.isdir", wraps=_isdir)

    results = list(completers.cd_completer(""))
    assert results == [f"{x}{os.sep}" for x in _listdir("x")]

    results = list(completers.cd_completer(os.path.join("sub", "f")))
    assert results == [f"sub{os.sep}five{os.sep}"]

    results = list(completers.cd_completer(os.path.join("dir", "f")))
    assert results == [f"dir{os.sep}four{os.sep}", f"dir{os.sep}five{os.sep}"]

    results = list(completers.cd_completer(os.path.join("dir", "th")))
    assert results == [f"dir{os.sep}three{os.sep}"]

    results = list(completers.cd_completer(os.path.join("dir-not-found", "th")))
    assert not results


@dataclass
class Step:
    name: str

    @staticmethod
    def make(*names: str):
        return [Step(name=name) for name in names]


@dataclass
class Flow:
    steps: list[Step]
    root: str = "."


KNOWN_STEPS = [
    "Conan",
    "CMake",
    "Build",
    "Test",
    "SignExecutables",
    "Pack",
    "SignPackages",
    "StorePackages",
    "Upload",
]


@dataclass
class Parser:
    flow: Flow

    @staticmethod
    def make():
        return Parser(flow=Flow(steps=Step.make(*KNOWN_STEPS)))


def test_steps():
    parser = Parser.make()
    results = list(completers.step_completer("", parser))
    assert results == [
        "Conan",
        "CMake",
        "Build",
        "Test",
        "SignExecutables",
        "Pack",
        "SignPackages",
        "StorePackages",
        "Upload",
    ]

    results = list(completers.step_completer("S", parser))
    assert results == ["SignExecutables", "SignPackages", "StorePackages"]

    results = list(completers.step_completer("Build,Test,", parser))
    assert results == [
        "Build,Test,Conan",
        "Build,Test,CMake",
        "Build,Test,SignExecutables",
        "Build,Test,Pack",
        "Build,Test,SignPackages",
        "Build,Test,StorePackages",
        "Build,Test,Upload",
    ]

    results = list(completers.step_completer("Build,Test,B", parser))
    assert not results

    results = list(completers.step_completer("Build,Test,P", parser))
    assert results == ["Build,Test,Pack"]


def test_matrix_in_another_castle(mocker):
    parser = Parser.make()
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "./.flow/matrix.json": {
                    "matrix": {
                        "str": ["value-1", "value-2"],
                        "bool": [True, False],
                        "num": [101, 112, 113],
                    },
                },
            }
        ),
    )

    results = list(completers.matrix_completer("", parser))
    assert results == ["str=", "bool=", "num="]

    results = list(completers.matrix_completer("str", parser))
    assert results == ["str=value-1", "str=value-2"]

    results = list(completers.matrix_completer("b", parser))
    assert results == ["bool=ON", "bool=OFF"]

    results = list(completers.matrix_completer("bool=ON,", parser))
    assert results == ["bool=ON,str=", "bool=ON,bool=", "bool=ON,num="]

    results = list(completers.matrix_completer("bool=ON,num=11", parser))
    assert results == ["bool=ON,num=112", "bool=ON,num=113"]

    results = list(completers.matrix_completer("bool=ON,num=11,missing", parser))
    assert not results

    results = list(completers.matrix_completer("bool=ON,num=11,missing=val", parser))
    assert not results
