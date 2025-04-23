# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from proj_flow.api import env, init
from proj_flow.project import api
from proj_flow.project.cplusplus import cmake_context

from ..load_flow_cfg import flow_cfg  # noqa: F401 pylint: disable=unused-import
from ..mocks import FsData, fs


# pylint: disable-next=redefined-outer-name
def test_cmake_postproc(mocker, flow_cfg: env.FlowConfig):  # noqa: F811
    files: FsData = {
        ".flow/config.yml": """LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1
LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2
LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3
LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4
LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5
"""
    }
    mocker.patch("builtins.open", wraps=fs(files))
    rt = env.Runtime.from_flow_cfg(flow_cfg)

    try:
        cmake_init = next(
            filter(lambda step: isinstance(step, cmake_context.CMakeInit), init.__steps)
        )
    except StopIteration:
        assert False

    assert cmake_init

    cmake_init.postprocess(rt, {"with": {"cmake": True}})
    assert (
        files[".flow/config.yml"]
        == """LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1
LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2
LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3
LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4
LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5
"""
    )

    files[
        ".flow/config.yml"
    ] = """LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1
LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2
LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3

shortcuts:
LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4
LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5
"""

    cmake_init.postprocess(rt, {"with": {"cmake": False}})
    assert (
        files[".flow/config.yml"]
        == """LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1
LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2
LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3

shortcuts:
LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4
LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5
"""
    )

    cmake_init.postprocess(
        rt, {"with": {"cmake": True}, "NAME_PREFIX": "(NAME_PREFIX)"}
    )
    assert (
        files[".flow/config.yml"]
        == """LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1 LINE1
LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2 LINE2
LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3 LINE3
cmake:
  vars:
    (NAME_PREFIX)_COVERAGE: "?config:coverage"
    (NAME_PREFIX)_SANITIZE: "?config:sanitizer"
    (NAME_PREFIX)_CUTDOWN_OS: "?runtime:cutdown_os"

shortcuts:
LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4 LINE4
LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5 LINE5
"""
    )


def test_cpp_plugins():
    cxx = api.get_project_type("cxx")

    with_github = cxx.get_extension_list({"with": {"github": {"actions": True}}})
    without_github = cxx.get_extension_list({"with": {"github": {"actions": False}}})

    assert with_github == [
        "proj_flow.ext.cplusplus",
        "proj_flow.ext.sign",
        "proj_flow.ext.store",
        "proj_flow.ext.github",
    ]
    assert without_github == [
        "proj_flow.ext.cplusplus",
        "proj_flow.ext.sign",
        "proj_flow.ext.store",
    ]
