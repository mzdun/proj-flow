# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import collections
import json
from typing import Any, Dict, List

import pytest

from proj_flow.api import env

KeyedValue = Dict[str, Any]
ConfigTest = collections.namedtuple("ConfigTest", ["data", "expected", "paths"])


DATA: List[ConfigTest] = [
    ConfigTest(
        "{}",
        {
            "os": "",
            "compiler": [],
            "build_type": "",
            "build_name": "",
            "build_dir": "build/",
            "preset": "",
            "build_generator": "",
        },
        {
            "os": None,
            "compiler": None,
            "build_type": None,
            "build_name": None,
            "build_dir": None,
            "preset": None,
            "build_generator": None,
        },
    ),
    ConfigTest(
        """
        {
            "os": "linux",
            "compiler": "gcc",
            "build_type": "Debug",
            "build_name": "linux-gcc-Debug",
            "preset": "__debug",
            "build_generator": "ninja",
            "outer": {
                "inner": {
                    "value": 2.71
                }
            }
        }
        """,
        {
            "os": "linux",
            "compiler": "gcc",
            "build_type": "Debug",
            "build_name": "linux-gcc-Debug",
            "build_dir": "build/__debug",
            "preset": "__debug",
            "build_generator": "ninja",
        },
        {
            "build_generator": "ninja",
            "build_generator.nonexistent": None,
            "os.nonexistent": None,
            "outer.inner.value": 2.71,
        },
    ),
]


@pytest.mark.parametrize("data,expected,paths", DATA)
def test_configs(data: str, expected: KeyedValue, paths: KeyedValue):
    items = json.loads(data)
    cfg = env.Config(items, [])

    for key, exp in expected.items():
        actual = getattr(cfg, key)
        assert key == key and actual == exp  # pylint: disable=comparison-with-itself

    for key, exp in paths.items():
        actual = cfg.get_path(key)
        assert key == key and actual == exp  # pylint: disable=comparison-with-itself
