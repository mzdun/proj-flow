# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.base.plugins** provide the plugin enumeration helpers.
"""

import json
from pathlib import Path
from typing import cast

import yaml

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader


def load_yaml(filename: Path):
    with open(filename) as src:
        return cast(dict, yaml.load(src, Loader=Loader))


def load_json(filename: Path):
    with open(filename) as src:
        return cast(dict, json.load(src))


LOADERS = {
    ".json": load_json,
    ".yml": load_yaml,
    ".yaml": load_yaml,
}


def load_data(filename: Path):
    ext = filename.suffix
    loader = LOADERS.get(ext.lower())
    if loader:
        try:
            return loader(filename)
        except Exception:
            pass

    for new_ext, loader in LOADERS.items():
        new_filename = filename.with_suffix(new_ext)
        try:
            return loader(new_filename)
        except Exception:
            pass

    return {}
