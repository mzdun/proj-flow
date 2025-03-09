# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import collections
from typing import List

from proj_flow.api import ctx
from proj_flow.project import interact


def test_move_to_front():
    assert ctx.move_to_front("c", ["a", "b", "c", "d"]) == ["c", "a", "b", "d"]
    assert ctx.move_to_front("c", ["a", "b", "C", "d"]) == ["a", "b", "C", "d"]
    assert ctx.move_to_front("c", ["a", "b", None, "d"]) == ["a", "b", "d"]


def _get_default(setting: ctx.Setting, settings: ctx.SettingsType):
    value = setting.calc_value(settings)
    if isinstance(value, list):
        return value[0] if value else False
    return value


Pipe = collections.namedtuple("Pipe", ["returncode", "stdout"])


def _faux_git(app: str, *args: str, capture_output=False):
    if app != "git" or len(args) != 2 or args[0] != "config" or not capture_output:
        return None
    if args[1] == "user.email":
        return Pipe(returncode=0, stdout="user@example.com\n")
    if args[1] == "user.name":
        return Pipe(returncode=0, stdout="User Name\n")
    return Pipe(returncode=1, stdout="\n")


def _prepare_settings(mocker):
    mocker.patch("proj_flow.base.cmd.run", wraps=_faux_git)
    mocker.patch("uuid.uuid4", wraps=lambda: "0d7954ff-5939-4379-a31a-580f45775cbe")

    ctx.register_init_setting(
        ctx.Setting("bad.git", "", value=ctx._git_config("abra.cadabra")),
        project="Testing",
    )

    ctx.register_common_init_setting(
        ctx.Setting("FAULTY.KEY", "", value="not-a-dict"),
        ctx.Setting("FAULTY.VALUE", "", fix="{FAULTY.KEY$map:faulty}"),
        ctx.Setting("FAULTY.EMPTY", "", fix="{$safe}"),
    )

    ctx.register_internal("faulty", "string instead of dict")

    ctx.register_common_switch("SWITCH.OFF", "", enabled=False)


def _read_settings():
    settings: ctx.SettingsType = {}
    for setting in ctx.defaults:
        settings[setting.json_key] = _get_default(setting, settings)
    for setting in ctx.switches:
        settings[setting.json_key] = _get_default(setting, settings)
    for setting in ctx.hidden:
        value = _get_default(setting, settings)
        if isinstance(value, bool) or value != "":
            settings[setting.json_key] = value

    for coll in [ctx.defaults, ctx.hidden]:
        for setting in coll:
            interact._fixup(
                settings, setting.json_key, setting.fix or "", setting.force_fix
            )

    return settings


def test_settings_eval(mocker):
    _prepare_settings(mocker)
    settings = _read_settings()

    assert settings == {
        "${": "${",
        "CMAKE_VERSION": "3.28",
        "COPY.HOLDER": "User Name",
        "COPY.LICENSE": "MIT",
        "COPY.YEAR": "2025",
        "EXT": ".cpp",
        "EXT.cxx": ".cpp",
        "EXT.hxx": ".hpp",
        "FAULTY.EMPTY": "",
        "FAULTY.KEY": "not-a-dict",
        "FAULTY.VALUE": "",
        "INCLUDE_PREFIX": "proj-flow",
        "INCLUDEDIR": "include/proj-flow",
        "NAME_PREFIX": "PROJ_FLOW",
        "NAMESPACE": "proj_flow",
        "PROJECT.DESCRIPTION": "",
        "PROJECT.EMAIL": "user@example.com",
        "PROJECT.NAME": "proj-flow",
        "PROJECT.TYPE": "console-application",
        "PROJECT.WIX.UPGRADE_GUID": "0d7954ff-5939-4379-a31a-580f45775cbe",
        "SRCDIR": "src",
        "SWITCH.OFF": False,
        "__flow_version__": "0.16.0",
        "bad.git": "",
        "cmake": {
            "application": True,
            "cmd": "add_executable",
            "console": True,
            "console-application": True,
            "link_access": "PRIVATE",
            "type": "",
        },
        "fubar.key": "",
        "fubar.switch": False,
        "with.cmake": True,
        "with.conan": True,
    }


def _faux_walk(_root: str) -> List[tuple]:
    return []


def test_settings_no_license(mocker):
    mocker.patch("os.walk", wraps=_faux_walk)
    _prepare_settings(mocker)
    settings = _read_settings()

    assert settings == {
        "${": "${",
        "CMAKE_VERSION": "3.28",
        "COPY.HOLDER": "User Name",
        "COPY.LICENSE": False,
        "COPY.YEAR": "2025",
        "EXT": ".cpp",
        "EXT.cxx": ".cpp",
        "EXT.hxx": ".hpp",
        "FAULTY.EMPTY": "",
        "FAULTY.KEY": "not-a-dict",
        "FAULTY.VALUE": "",
        "INCLUDE_PREFIX": "proj-flow",
        "INCLUDEDIR": "include/proj-flow",
        "NAME_PREFIX": "PROJ_FLOW",
        "NAMESPACE": "proj_flow",
        "PROJECT.DESCRIPTION": "",
        "PROJECT.EMAIL": "user@example.com",
        "PROJECT.NAME": "proj-flow",
        "PROJECT.TYPE": "console-application",
        "PROJECT.WIX.UPGRADE_GUID": "0d7954ff-5939-4379-a31a-580f45775cbe",
        "SRCDIR": "src",
        "SWITCH.OFF": False,
        "__flow_version__": "0.16.0",
        "bad.git": "",
        "cmake": {
            "application": True,
            "cmd": "add_executable",
            "console": True,
            "console-application": True,
            "link_access": "PRIVATE",
            "type": "",
        },
        "fubar.key": "",
        "fubar.switch": False,
        "with.cmake": True,
        "with.conan": True,
    }
