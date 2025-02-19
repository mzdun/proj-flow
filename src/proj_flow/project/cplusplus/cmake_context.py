# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.cplusplus.cmake.context** provides CMake-specific
initialization context.
"""

import re
import uuid

import chevron

from proj_flow import api, project
from proj_flow.base.__cmake_version__ import CMAKE_VERSION
from proj_flow.project import data
from proj_flow.project.cplusplus import project

config_json_mustache = """
{{#with_cmake}}
cmake:
  vars:
    {{NAME_PREFIX}}_COVERAGE: "?config:coverage"
    {{NAME_PREFIX}}_SANITIZE: "?config:sanitizer"
    {{NAME_PREFIX}}_CUTDOWN_OS: "?runtime:cutdown_os"
{{/with_cmake}}
"""


class CMakeInit(api.init.InitStep):
    def postprocess(self, rt: api.env.Runtime, context: dict):
        patch = chevron.render(config_json_mustache, context).rstrip()
        if not patch:
            return

        with open(".flow/config.yml", encoding="UTF-8") as config_file:
            patched = re.split(r"(\n\nshortcuts:\n)", config_file.read())

        if len(patched) != 3:
            return

        patched.insert(1, patch)
        content = "".join(patched)

        with open(".flow/config.yml", "w", encoding="UTF-8") as config_file:
            config_file.write(content)


def _list_cmake_types():
    return api.ctx.move_to_front(
        "console-application",
        sorted(key for key in data.get_internal("cmake").keys() if key),
    )


api.init.register_init_step(CMakeInit())

project.cxx.register_init_setting(
    api.ctx.Setting("PROJECT.TYPE", "CMake project type", _list_cmake_types)
)
project.cxx.register_init_setting(
    api.ctx.Setting("cmake", fix="{PROJECT.TYPE$map:cmake}"),
    api.ctx.Setting("CMAKE_VERSION", value=CMAKE_VERSION),
    api.ctx.Setting("PROJECT.WIX.UPGRADE_GUID", value=lambda: str(uuid.uuid4())),
    is_hidden=True,
)
project.cxx.register_switch("with_cmake", "Use CMake", True)
project.cxx.register_internal(
    "cmake",
    {
        "": {"cmd": "add_executable", "type": ""},
        "console-application": {
            "cmd": "add_executable",
            "type": "",
            "console-application": True,
            "console": True,
            "application": True,
            "link_access": "PRIVATE",
        },
        "win32-application": {
            "cmd": "add_executable",
            "type": " WIN32",
            "win32-application": True,
            "win32": True,
            "application": True,
            "link_access": "PRIVATE",
        },
        "static-library": {
            "cmd": "add_library",
            "type": " STATIC",
            "static-library": True,
            "static": True,
            "library": True,
            "link_access": "PUBLIC",
        },
        "shared-library": {
            "cmd": "add_library",
            "type": " SHARED",
            "shared-library": True,
            "shared": True,
            "library": True,
            "link_access": "PUBLIC",
        },
        "plugin-library": {
            "cmd": "add_library",
            "type": " MODULE",
            "plugin-library": True,
            "plugin": True,
            "library": True,
            "link_access": "PUBLIC",
        },
    },
)
