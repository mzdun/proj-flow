# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
from typing import Callable, Dict, Iterable, List

from cxx_flow.api import ctx
from cxx_flow.base import cmd


def _fixup(settings: ctx.SettingsType, key: str, fixup: str, force=False):
    value = settings.get(key, "")
    if value != "" and not force:
        return

    value = ctx._build_fixup(settings, fixup)
    settings[key] = value


def _get_default(setting: ctx.Setting, settings: ctx.SettingsType):
    value = setting.calc_value(settings)
    if isinstance(value, list):
        return value[0]
    return value


def all_default():
    settings: ctx.SettingsType = {}

    for setting in ctx.defaults:
        value = _get_default(setting, settings)
        settings[setting.json_key] = value

    for setting in ctx.switches:
        value = _get_default(setting, settings)
        settings[setting.json_key] = value

    return settings


def fixup(settings: ctx.SettingsType):
    for setting in ctx.hidden:
        value = _get_default(setting, settings)
        if isinstance(value, bool) or value != "":
            settings[setting.json_key] = value

    for coll in [ctx.defaults, ctx.hidden]:
        for setting in coll:
            _fixup(settings, setting.json_key, setting.fix or "", setting.force_fix)
    del settings["EXT"]

    result = {}
    for key in settings:
        path = key.split(".")
        path_ctx = result
        for step in path[:-1]:
            if step not in path_ctx or not isinstance(path_ctx[step], dict):
                path_ctx[step] = {}
            path_ctx = path_ctx[step]
        path_ctx[path[-1]] = settings[key]
    return result


def get_internal(key: str, value: any = None):
    return ctx.internals.get(key, value)
