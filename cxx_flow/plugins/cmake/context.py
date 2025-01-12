# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import pprint
import re

import chevron

from cxx_flow.flow import config, ctx, init

from .__version__ import CMAKE_VERSION

config_json_mustache = """
{{#with_cmake}}
    "cmake": {
        "vars": {
            "{{NAME_PREFIX}}_COVERAGE": "?config:coverage",
            "{{NAME_PREFIX}}_SANITIZE": "?config:sanitizer",
            "{{NAME_PREFIX}}_CUTDOWN_OS": "?runtime:cutdown_os"
        }
    },
{{/with_cmake}}
"""


class CMakeInit(init.InitStep):
    def postprocess(self, rt: config.Runtime, context: dict):
        patch = chevron.render(config_json_mustache, context).rstrip()
        if not patch:
            return

        with open(".flow/config.json", encoding="UTF-8") as config_file:
            patched = re.split(r'(\s*"shortcuts":\s*{)', config_file.read())

        if len(patched) != 3:
            return

        patched.insert(1, patch)
        content = "".join(patched)

        with open(".flow/config.json", "w", encoding="UTF-8") as config_file:
            config_file.write(content)


def _list_cmake_types():
    return ctx.move_to_front(
        "console-application",
        sorted(key for key in ctx.get_internal("cmake").keys() if key),
    )


init.register_init_step(CMakeInit())
ctx.register_init_setting(
    ctx.Setting("PROJECT.TYPE", "CMake project type", _list_cmake_types)
)
ctx.register_init_setting(
    ctx.Setting("cmake", fix="{PROJECT.TYPE$map:cmake}"),
    ctx.Setting("CMAKE_VERSION", value=CMAKE_VERSION),
    is_hidden=True,
)
ctx.register_switch("with_cmake", "Use CMake", True)
ctx.register_internal(
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
        "macos-application": {
            "cmd": "add_executable",
            "type": " MACOSX_BUNDLE",
            "macos-application": True,
            "macos": True,
            "bundle": True,
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
