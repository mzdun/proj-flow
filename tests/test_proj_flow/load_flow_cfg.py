# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import json
from typing import Dict, Union

import pytest

from proj_flow.api import env
from proj_flow.flow import steps

from .mocks import fs

CONFIG = json.dumps(
    {
        "entry": {"alias": ["Default", "PropA", "PropB"]},
        "shortcuts": {
            "tested": {"a": "b", "c": "d"},
            "unused": {"switch": False, "c": ["d", "f", "g"]},
        },
        "compiler": {"os-default": {"test-os": "test-compiler"}},
    }
)

MATRIX = json.dumps(
    {"matrix": {"a": ["b", "e"], "c": ["d", "f"], "switch": [True, False]}}
)


def load_flow_cfg(
    mocker,
    user_cfg: Union[dict, str, None],
    proj_cfg: Union[dict, str, None],
    matrix: Union[dict, str, None] = None,
    root="/<project-root>",
):
    files: Dict[str, Union[dict, str, bytes]] = {}
    if user_cfg is not None:
        files["<user-home>/.config/proj-flow.json"] = user_cfg
    if proj_cfg is not None:
        files[f"{root}/.flow/config.json"] = proj_cfg
    if matrix is not None:
        files[f"{root}/.flow/matrix.json"] = matrix
    mocker.patch("builtins.open", wraps=fs(files))
    mocker.patch("os.path.expanduser", wraps=lambda _: "<user-home>")

    def is_directory(path: str):
        return path == f"{root}/.flow/extensions"

    mocker.patch("os.path.isdir", wraps=is_directory)

    cfg = env.FlowConfig.load(root=root)
    entries = cfg.entry
    cfg.aliases = [env.RunAlias.from_json(key, entries[key]) for key in entries]
    return cfg


@pytest.fixture
def flow_cfg(mocker):
    mocker.patch("os.chdir", wraps=lambda _: ".")
    mocker.patch("os.getcwd", wraps=lambda: "/<project>")
    env.platform = "test-os"
    result = load_flow_cfg(mocker, user_cfg=None, proj_cfg=CONFIG, matrix=MATRIX)
    steps.clean_aliases(result)
    return result
