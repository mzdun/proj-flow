# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from unittest.mock import Mock

from proj_flow.api import env
from proj_flow.project import api, interact

from ..load_flow_cfg import flow_cfg  # noqa: F401 pylint: disable=unused-import
from ..mocks import FsData, fs
from . import project_fubar


def test_no_project():
    try:
        api.get_project_type("xyzyy")
        assert False
    except api.ProjectNotFound:
        assert True


def _faux_context(*_args, **_kwargs):
    return {
        "key1": "value",
        "key2": {
            "key2a": True,
            "key2b": 123,
        },
    }


# pylint: disable-next=redefined-outer-name
def test_base_project(mocker, flow_cfg: env.FlowConfig):  # noqa: F811
    files: FsData = {
        ".flow/config.yml": """LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1
LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2
LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3
LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4
LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5
"""
    }
    get_context: Mock = mocker.patch(
        "proj_flow.project.interact.get_context", wraps=_faux_context
    )
    mocker.patch("builtins.open", wraps=fs(files))
    try:
        proj = api.get_project_type("foo-bar")
        assert proj
    except api.ProjectNotFound:
        assert False

    setup = interact.ContextSetup(
        dest_path=None, interactive=False, simple=True, load=None
    )
    rt = env.Runtime.from_flow_cfg(flow_cfg)
    context = proj.get_context(setup, rt)

    assert proj.id == "foo-bar"
    assert isinstance(proj, project_fubar.FubarProject)
    assert context == {
        "key1": "value",
        "key2": {
            "key2a": True,
            "key2b": 123,
        },
    }
    get_context.assert_called_once_with(setup, "foo-bar", rt)

    proj.append_extensions({"no-exts": True})
    assert (
        files[".flow/config.yml"]
        == """LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1
LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2
LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3
LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4
LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5
"""
    )
    proj.append_extensions(context)
    assert (
        files[".flow/config.yml"]
        == """extensions:
  - package.ext.extension-1
  - package.ext.extension-2

LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1
LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2
LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3
LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4
LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5
"""
    )
