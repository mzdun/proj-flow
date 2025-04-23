# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from proj_flow.api import env
from proj_flow.flow import configs

from ..capture import Capture
from ..mocks import fs

DATA = [
    env.Config(
        items={"key-1": "value-1", "key-2": True, "key-3": 1},
        keys=["key-1", "key-2", "key-3"],
    ),
    env.Config(
        items={"key-1": "value-2", "key-2": True, "key-3": 1},
        keys=["key-1", "key-2", "key-3"],
    ),
    env.Config(
        items={"key-1": "value-1", "key-2": False, "key-3": 1},
        keys=["key-1", "key-2", "key-3"],
    ),
    env.Config(
        items={"key-1": "value-2", "key-2": False, "key-3": 1},
        keys=["key-1", "key-2", "key-3"],
    ),
    env.Config(
        items={"key-1": "value-1", "key-2": True, "key-3": 2},
        keys=["key-1", "key-2", "key-3"],
    ),
    env.Config(
        items={"key-1": "value-2", "key-2": True, "key-3": 2},
        keys=["key-1", "key-2", "key-3"],
    ),
    env.Config(
        items={"key-1": "value-1", "key-2": False, "key-3": 2},
        keys=["key-1", "key-2", "key-3"],
    ),
    env.Config(
        items={"key-1": "value-2", "key-2": False, "key-3": 2},
        keys=["key-1", "key-2", "key-3"],
    ),
    env.Config(
        items={"key-1": "value-1", "key-2": True, "key-3": 3},
        keys=["key-1", "key-2", "key-3"],
    ),
    env.Config(
        items={"key-1": "value-2", "key-2": True, "key-3": 3},
        keys=["key-1", "key-2", "key-3"],
    ),
    env.Config(
        items={"key-1": "value-1", "key-2": False, "key-3": 3},
        keys=["key-1", "key-2", "key-3"],
    ),
    env.Config(
        items={"key-1": "value-2", "key-2": False, "key-3": 3},
        keys=["key-1", "key-2", "key-3"],
    ),
]


def test_configs(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "./.flow/matrix.yml": {
                    "matrix": {
                        "key-1": ["value-1", "value-2"],
                        "key-2": [True, False],
                        "key-3": [1, 2, 3],
                    }
                }
            }
        ),
    )

    rt = env.Runtime()
    result = configs.Configs(rt, [])

    assert result.usable == DATA


def test_configs_cli(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "./.flow/matrix.yml": {
                    "matrix": {
                        "key-1": ["value-1", "value-2"],
                        "key-2": [True, False],
                        "key-3": [1, 2, 3],
                    }
                }
            }
        ),
    )

    rt = env.Runtime()
    result = configs.Configs(
        rt, ["key-1=value-1", "key-2=with-key-2", "key-3=2", "key-2=no"]
    )

    assert result.usable == [
        env.Config(
            items={"key-1": "value-1", "key-2": True, "key-3": 2},
            keys=["key-1", "key-2", "key-3"],
        ),
        env.Config(
            items={"key-1": "value-1", "key-2": False, "key-3": 2},
            keys=["key-1", "key-2", "key-3"],
        ),
    ]


def test_configs_cli_bad(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "./.flow/matrix.yml": {
                    "matrix": {
                        "key-1": ["value-1", "value-2"],
                        "key-2": [True, False],
                        "key-3": [1, 2, 3],
                    }
                }
            }
        ),
    )

    rt = env.Runtime()
    result = configs.Configs(rt, ["key-1", "--key-2=with-key-2"])

    assert result.usable == DATA


def test_configs_cli_not_an_int(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "./.flow/matrix.yml": {
                    "matrix": {
                        "key-1": ["value-1", "value-2"],
                        "key-2": [True, False],
                        "key-3": [1, 2, 3],
                    }
                }
            }
        ),
    )

    rt = env.Runtime()
    result = configs.Configs(rt, ["key-3=number"])

    assert not result.usable


def test_configs_cxx(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "./.flow/matrix.yml": {
                    "matrix": {
                        "compiler": ["gcc", "msvc"],
                        "os": ["ubuntu", "windows"],
                        "build_type": ["debug", "release"],
                        "coverage": [True, False],
                    },
                    "exclude": [
                        {"compiler": "gcc", "os": "windows"},
                        {"compiler": "msvc", "os": "ubuntu"},
                    ],
                }
            }
        ),
    )

    with Capture() as capture:
        rt = env.Runtime(
            cfg={
                "compiler": {
                    "names": {"gcc": ["gcc", "g++"]},
                    "os-default": {"ubuntu": "gcc", "windows": "msvc"},
                }
            },
            no_coverage=True,
            official=True,
        )
        result = configs.Configs(rt, ["compiler=gcc"])

    assert capture.stdout == ""
    assert capture.stderr == ""
    assert result.usable == [
        env.Config(
            items={
                "compiler": ["gcc", "g++"],
                "os": "ubuntu",
                "build_type": "debug",
                "github_os": "ubuntu-latest",
                "build_name": "debug with gcc on ubuntu",
                "needs_gcc_ppa": False,
                "--orig-compiler": "gcc",
            },
            keys=["compiler", "os", "build_type"],
        ),
        env.Config(
            items={
                "compiler": ["gcc", "g++"],
                "os": "ubuntu",
                "build_type": "release",
                "github_os": "ubuntu-latest",
                "build_name": "release with gcc on ubuntu",
                "needs_gcc_ppa": False,
                "--orig-compiler": "gcc",
            },
            keys=["compiler", "os", "build_type"],
        ),
    ]


def test_configs_cxx_dont_expand(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "./.flow/matrix.yml": {
                    "matrix": {
                        "compiler": ["gcc", "msvc"],
                        "os": ["ubuntu", "windows"],
                        "build_type": ["debug", "release"],
                    },
                    "exclude": [
                        {"compiler": "gcc", "os": "windows"},
                        {"compiler": "msvc", "os": "ubuntu"},
                    ],
                }
            }
        ),
    )

    with Capture() as capture:
        rt = env.Runtime(
            cfg={
                "compiler": {
                    "names": {"gcc": ["gcc", "g++"]},
                    "os-default": {"ubuntu": "gcc", "windows": "msvc"},
                }
            }
        )
        result = configs.Configs(rt, ["compiler=gcc"], expand_compilers=False)

    assert capture.stdout == ""
    assert capture.stderr == ""
    assert result.usable == [
        env.Config(
            items={
                "compiler": "gcc",
                "os": "ubuntu",
                "build_type": "debug",
                "github_os": "ubuntu-latest",
                "build_name": "debug with gcc on ubuntu",
                "needs_gcc_ppa": False,
            },
            keys=["compiler", "os", "build_type"],
        ),
        env.Config(
            items={
                "compiler": "gcc",
                "os": "ubuntu",
                "build_type": "release",
                "github_os": "ubuntu-latest",
                "build_name": "release with gcc on ubuntu",
                "needs_gcc_ppa": False,
            },
            keys=["compiler", "os", "build_type"],
        ),
    ]


def test_configs_cxx_all_compilers(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "./.flow/matrix.yml": {
                    "matrix": {
                        "compiler": ["gcc", "msvc"],
                        "os": ["ubuntu", "windows"],
                        "build_type": ["debug", "release"],
                    },
                    "exclude": [
                        {"compiler": "gcc", "os": "windows"},
                        {"compiler": "msvc", "os": "ubuntu"},
                    ],
                }
            }
        ),
    )

    with Capture() as capture:
        rt = env.Runtime(
            cfg={
                "compiler": {
                    "names": {"gcc": ["gcc", "g++"]},
                    "os-default": {"ubuntu": "gcc", "windows": "msvc"},
                },
                "lts": {"ubuntu": ["16.04", "18.04", "20.04"]},
            }
        )
        result = configs.Configs(rt, ["os=ubuntu"])

    assert capture.stdout == ""
    assert (
        capture.stderr == "\x1b[1;33m-- lts.ubuntu in config.yaml is deprecated; "
        "please remove it, so it can be calculated based on current date\x1b[m\n"
    )
    assert result.usable == [
        env.Config(
            items={
                "compiler": ["gcc", "g++"],
                "os": "ubuntu",
                "build_type": "debug",
                "github_os": "ubuntu-latest",
                "build_name": "debug with gcc on ubuntu",
                "needs_gcc_ppa": False,
                "--orig-compiler": "gcc",
            },
            keys=["compiler", "os", "build_type"],
        ),
        env.Config(
            items={
                "compiler": ["gcc", "g++"],
                "os": "ubuntu",
                "build_type": "release",
                "github_os": "ubuntu-latest",
                "build_name": "release with gcc on ubuntu",
                "needs_gcc_ppa": False,
                "--orig-compiler": "gcc",
            },
            keys=["compiler", "os", "build_type"],
        ),
    ]


def test_configs_cxx_spread_lts(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "./.flow/matrix.yml": {
                    "matrix": {
                        "compiler": ["gcc", "msvc"],
                        "os": ["ubuntu", "windows"],
                        "build_type": ["debug", "release"],
                        "sanitizer": [True, False],
                    },
                    "exclude": [
                        {"compiler": "gcc", "os": "windows"},
                        {"compiler": "msvc", "os": "ubuntu"},
                    ],
                }
            }
        ),
    )

    env.platform = "ubuntu"
    with Capture() as capture:
        rt = env.Runtime(
            cfg={
                "compiler": {
                    "names": {"gcc": ["gcc", "g++"]},
                    "os-default": {"ubuntu": "gcc", "windows": "msvc"},
                }
            },
            official=True,
            only_host=True,
        )
        result = configs.Configs(rt, ["compiler=gcc"], spread_lts=True)

    assert capture.stdout == ""
    assert capture.stderr == ""
    assert result.usable == [
        env.Config(
            items={
                "compiler": ["gcc", "g++"],
                "os": "ubuntu",
                "build_type": "debug",
                "sanitizer": True,
                "github_os": "ubuntu-22.04",
                "build_name": "debug with gcc on ubuntu-22.04 (and sanitizer)",
                "needs_gcc_ppa": True,
                "--orig-compiler": "gcc",
            },
            keys=["compiler", "os", "build_type", "sanitizer"],
        ),
        env.Config(
            items={
                "compiler": ["gcc", "g++"],
                "os": "ubuntu",
                "build_type": "debug",
                "sanitizer": True,
                "github_os": "ubuntu-24.04",
                "build_name": "debug with gcc on ubuntu-24.04 (and sanitizer)",
                "needs_gcc_ppa": True,
                "--orig-compiler": "gcc",
            },
            keys=["compiler", "os", "build_type", "sanitizer"],
        ),
        env.Config(
            items={
                "compiler": ["gcc", "g++"],
                "os": "ubuntu",
                "build_type": "release",
                "sanitizer": True,
                "github_os": "ubuntu-22.04",
                "build_name": "release with gcc on ubuntu-22.04 (and sanitizer)",
                "needs_gcc_ppa": True,
                "--orig-compiler": "gcc",
            },
            keys=["compiler", "os", "build_type", "sanitizer"],
        ),
        env.Config(
            items={
                "compiler": ["gcc", "g++"],
                "os": "ubuntu",
                "build_type": "release",
                "sanitizer": True,
                "github_os": "ubuntu-24.04",
                "build_name": "release with gcc on ubuntu-24.04 (and sanitizer)",
                "needs_gcc_ppa": True,
                "--orig-compiler": "gcc",
            },
            keys=["compiler", "os", "build_type", "sanitizer"],
        ),
        env.Config(
            items={
                "compiler": ["gcc", "g++"],
                "os": "ubuntu",
                "build_type": "debug",
                "sanitizer": False,
                "github_os": "ubuntu-22.04",
                "build_name": "debug with gcc on ubuntu-22.04",
                "needs_gcc_ppa": True,
                "--orig-compiler": "gcc",
            },
            keys=["compiler", "os", "build_type", "sanitizer"],
        ),
        env.Config(
            items={
                "compiler": ["gcc", "g++"],
                "os": "ubuntu",
                "build_type": "debug",
                "sanitizer": False,
                "github_os": "ubuntu-24.04",
                "build_name": "debug with gcc on ubuntu-24.04",
                "needs_gcc_ppa": True,
                "--orig-compiler": "gcc",
            },
            keys=["compiler", "os", "build_type", "sanitizer"],
        ),
        env.Config(
            items={
                "compiler": ["gcc", "g++"],
                "os": "ubuntu",
                "build_type": "release",
                "sanitizer": False,
                "github_os": "ubuntu-22.04",
                "build_name": "release with gcc on ubuntu-22.04",
                "needs_gcc_ppa": True,
                "--orig-compiler": "gcc",
            },
            keys=["compiler", "os", "build_type", "sanitizer"],
        ),
        env.Config(
            items={
                "compiler": ["gcc", "g++"],
                "os": "ubuntu",
                "build_type": "release",
                "sanitizer": False,
                "github_os": "ubuntu-24.04",
                "build_name": "release with gcc on ubuntu-24.04",
                "needs_gcc_ppa": True,
                "--orig-compiler": "gcc",
            },
            keys=["compiler", "os", "build_type", "sanitizer"],
        ),
    ]
