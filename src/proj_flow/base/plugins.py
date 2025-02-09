# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.base.plugins** provide the plugin enumeration helpers.
"""

import json
import os
from typing import cast

import yaml


def load_yaml(filename: str):
    with open(filename) as src:
        return cast(dict, yaml.load(src, Loader=yaml.Loader))


def load_json(filename: str):
    with open(filename) as src:
        return cast(dict, json.load(src))


LOADERS = {
    ".json": load_json,
    ".yml": load_yaml,
    ".yaml": load_yaml,
}


def load_data(filename: str):
    prefix, ext = os.path.splitext(filename)
    loader = LOADERS.get(ext.lower())
    if loader:
        try:
            return loader(filename)
        except Exception:
            pass

    for new_ext, loader in LOADERS.items():
        new_filename = prefix + new_ext
        try:
            return loader(new_filename)
        except Exception:
            pass

    return {}
