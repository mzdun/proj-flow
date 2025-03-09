# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
import sys

from proj_flow.api import env

from ..capture import Capture
from ..load_flow_cfg import load_flow_cfg


def test_flow_outside_project(mocker):
    cfg = load_flow_cfg(mocker, user_cfg="false", proj_cfg=None)
    assert cfg._cfg == {"defaults": {}}
    assert not cfg.aliases
    assert not cfg.steps
    assert not cfg.entry
    assert not cfg.compiler
    assert not cfg.compiler_names
    assert not cfg.compiler_os_default
    assert not cfg.lts_list
    assert not cfg.postproc
    assert not cfg.postproc_exclude
    assert not cfg.shortcuts


def test_flow_inside_project(mocker):
    cfg = load_flow_cfg(
        mocker,
        user_cfg=None,
        proj_cfg={
            "extensions": ["proj_flow.maximal"],
            "entry": {
                "build": {"doc": "documentation override", "steps": ["Build"]},
                "config": ["Conan", "CMake"],
                "test": ["Build", "Test"],
                "verify": {
                    "steps": [
                        "Build",
                        "Test",
                        "Sign",
                        "Pack",
                        "SignPackages",
                        "Store",
                        "BinInst",
                        "DevInst",
                    ]
                },
            },
            "compiler": {
                "names": {
                    "clang": ["clang", "clang++"],
                    "gcc": ["gcc", "g++"],
                },
                "os-default": {"ubuntu": "gcc", "windows": "msvc"},
            },
            "lts": {"os": ["os-current", "os-previous"]},
            "postproc": {"exclude": [{"github_os": "ubuntu-24.04", "sanitizer": True}]},
            "shortcuts": {
                "dbg": {"build_type": "Debug", "sanitizer": False},
                "rel": {"build_type": "Release", "sanitizer": False},
                "both": {"build_type": ["Debug", "Release"], "sanitizer": False},
                "sane": {"build_type": "Debug", "sanitizer": True},
            },
        },
    )
    assert cfg._cfg == {
        "defaults": {},
        "extensions": ["proj_flow.minimal", "proj_flow.maximal"],
        "compiler": {
            "names": {"clang": ["clang", "clang++"], "gcc": ["gcc", "g++"]},
            "os-default": {"ubuntu": "gcc", "windows": "msvc"},
        },
        "entry": {
            "build": {"doc": "documentation override", "steps": ["Build"]},
            "config": ["Conan", "CMake"],
            "test": ["Build", "Test"],
            "verify": {
                "steps": [
                    "Build",
                    "Test",
                    "Sign",
                    "Pack",
                    "SignPackages",
                    "Store",
                    "BinInst",
                    "DevInst",
                ]
            },
        },
        "lts": {"os": ["os-current", "os-previous"]},
        "postproc": {"exclude": [{"github_os": "ubuntu-24.04", "sanitizer": True}]},
        "shortcuts": {
            "both": {"build_type": ["Debug", "Release"], "sanitizer": False},
            "dbg": {"build_type": "Debug", "sanitizer": False},
            "rel": {"build_type": "Release", "sanitizer": False},
            "sane": {"build_type": "Debug", "sanitizer": True},
        },
    }
    assert cfg.aliases == [
        env.RunAlias(name="build", doc="documentation override", steps=["Build"]),
        env.RunAlias(
            name="config",
            doc='Shortcut for "run -s Conan,CMake"',
            steps=["Conan", "CMake"],
        ),
        env.RunAlias(
            name="test", doc='Shortcut for "run -s Build,Test"', steps=["Build", "Test"]
        ),
        env.RunAlias(
            name="verify",
            doc='Shortcut for "run -s Build,Test,Sign,Pack,SignPackages,Store,BinInst,DevInst"',
            steps=[
                "Build",
                "Test",
                "Sign",
                "Pack",
                "SignPackages",
                "Store",
                "BinInst",
                "DevInst",
            ],
        ),
    ]
    assert not cfg.steps
    assert cfg.entry == {
        "build": {"doc": "documentation override", "steps": ["Build"]},
        "config": ["Conan", "CMake"],
        "test": ["Build", "Test"],
        "verify": {
            "steps": [
                "Build",
                "Test",
                "Sign",
                "Pack",
                "SignPackages",
                "Store",
                "BinInst",
                "DevInst",
            ]
        },
    }
    assert cfg.compiler == {
        "names": {"clang": ["clang", "clang++"], "gcc": ["gcc", "g++"]},
        "os-default": {"ubuntu": "gcc", "windows": "msvc"},
    }
    assert cfg.compiler_names == {"clang": ["clang", "clang++"], "gcc": ["gcc", "g++"]}
    assert cfg.compiler_os_default == {"ubuntu": "gcc", "windows": "msvc"}
    assert cfg.lts_list == {"os": ["os-current", "os-previous"]}
    assert cfg.postproc == {
        "exclude": [{"github_os": "ubuntu-24.04", "sanitizer": True}]
    }
    assert cfg.postproc_exclude == [{"github_os": "ubuntu-24.04", "sanitizer": True}]
    assert cfg.shortcuts == {
        "both": {"build_type": ["Debug", "Release"], "sanitizer": False},
        "dbg": {"build_type": "Debug", "sanitizer": False},
        "rel": {"build_type": "Release", "sanitizer": False},
        "sane": {"build_type": "Debug", "sanitizer": True},
    }


def test_flow_merge(mocker):
    cfg = load_flow_cfg(
        mocker,
        user_cfg={
            "entry": {
                "build": ["Build"],
                "config": ["M4"],
            },
            "compiler": {
                "names": {
                    "clang": ["bad", "worse++"],
                    "comp": ["c-comp", "cxx-comp"],
                },
            },
        },
        proj_cfg={
            "entry": {
                "config": ["Conan", "CMake"],
                "test": ["Build", "Test"],
                "verify": {
                    "steps": [
                        "Build",
                        "Test",
                        "Sign",
                        "Pack",
                        "SignPackages",
                        "Store",
                        "BinInst",
                        "DevInst",
                    ]
                },
            },
            "compiler": {
                "names": {
                    "clang": ["clang", "clang++"],
                    "gcc": ["gcc", "g++"],
                },
                "os-default": {"ubuntu": "gcc", "windows": "msvc"},
            },
            "lts": {"os": ["os-current", "os-previous"]},
            "postproc": {"exclude": [{"github_os": "ubuntu-24.04", "sanitizer": True}]},
            "shortcuts": {
                "dbg": {"build_type": "Debug", "sanitizer": False},
                "rel": {"build_type": "Release", "sanitizer": False},
                "both": {"build_type": ["Debug", "Release"], "sanitizer": False},
                "sane": {"build_type": "Debug", "sanitizer": True},
            },
        },
    )
    assert cfg._cfg == {
        "defaults": {},
        "compiler": {
            "names": {
                "clang": ["clang", "clang++"],
                "comp": ["c-comp", "cxx-comp"],
                "gcc": ["gcc", "g++"],
            },
            "os-default": {"ubuntu": "gcc", "windows": "msvc"},
        },
        "entry": {
            "build": ["Build"],
            "config": ["Conan", "CMake"],
            "test": ["Build", "Test"],
            "verify": {
                "steps": [
                    "Build",
                    "Test",
                    "Sign",
                    "Pack",
                    "SignPackages",
                    "Store",
                    "BinInst",
                    "DevInst",
                ]
            },
        },
        "lts": {"os": ["os-current", "os-previous"]},
        "postproc": {"exclude": [{"github_os": "ubuntu-24.04", "sanitizer": True}]},
        "shortcuts": {
            "both": {"build_type": ["Debug", "Release"], "sanitizer": False},
            "dbg": {"build_type": "Debug", "sanitizer": False},
            "rel": {"build_type": "Release", "sanitizer": False},
            "sane": {"build_type": "Debug", "sanitizer": True},
        },
    }


def test_flow_local_extension(mocker):
    root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "playground")
    mocker.patch("os.path.expanduser", wraps=lambda _: "<user-home>")
    with Capture() as console:
        cfg = env.FlowConfig.load(root=root)

    local_extensions = os.path.abspath(os.path.join(cfg.root, ".flow", "extensions"))
    print(sys.path)
    assert local_extensions in sys.path
    assert cfg._cfg["extensions"] == ["proj_flow.minimal", "playground_extension"]
    assert "playground_extension" in sys.modules
    assert "playground_extension was loaded\n" in console.stdout


def test_flow_defaults(mocker):
    cfg = load_flow_cfg(
        mocker,
        user_cfg={
            "defaults": {
                "USER": {"NAME": "User name", "FLAG": False},
                "FUNNY": {"LIST": ["a", 3, None], "NOTHING": None},
            }
        },
        proj_cfg=None,
    )
    assert cfg._cfg == {
        "defaults": {
            "FUNNY.LIST": "['a', 3, None]",
            "FUNNY.NOTHING": "",
            "USER.FLAG": False,
            "USER.NAME": "User name",
        }
    }
