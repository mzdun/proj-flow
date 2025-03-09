# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import json

import yaml

from proj_flow.base import plugins

from ..mocks import fs

DATA = {
    "root": ["a", "b", "c"],
    "dict": {
        "term": "explanation",
        "year": 2025,
    },
}

YAML = yaml.dump(DATA, Dumper=yaml.Dumper, indent=2)
JSON = json.dumps(DATA, indent=2)


def test_json_to_yaml(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs({"matrix.yaml": YAML}),
    )

    data = plugins.load_data("matrix.json")
    assert data == DATA


def test_json_to_yml(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs({"matrix.yml": YAML}),
    )

    data = plugins.load_data("matrix.json")
    assert data == DATA


def test_json_direct(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs({"matrix.json": JSON}),
    )

    data = plugins.load_data("matrix.json")
    assert data == DATA


def test_yaml_direct(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs({"matrix.yaml": YAML}),
    )

    data = plugins.load_data("matrix.yaml")
    assert data == DATA


def test_no_known_format(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs({"matrix.text": YAML}),
    )

    data = plugins.load_data("matrix.yaml")
    assert data == {}
