# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import datetime
import inspect
import os
from dataclasses import dataclass
from pprint import pprint
from typing import Callable, Dict, Iterable, List, Optional, Union

from . import cmd

StrOrBool = Union[str, bool]
Values = Union[StrOrBool, List[str]]
SettingsType = Dict[str, StrOrBool]


@dataclass
class Setting:
    json_key: str
    prompt: str = ""
    value: Union[Values, Callable[[], Values]] = ""
    fix: Optional[str] = None
    force_fix: bool = False

    def calc_value(self, previous: SettingsType):
        if isinstance(self.value, Callable):
            kwargs = {}

            params = inspect.signature(self.value).parameters
            if "settings" in params:
                kwargs["settings"] = previous

            return self.value(**kwargs)

        return self.value


package_root = os.path.dirname(os.path.dirname(__file__))
template_dir = os.path.join("data", "template")


_fileext = {".cc": ".hh", ".cxx": ".hxx", ".cpp": ".hpp"}


def _git_config(name: str):
    def wrap():
        proc = cmd.run("git", "config", name, capture_output=True)
        if proc is None or proc.returncode != 0:
            return None
        return proc.stdout.strip()

    return wrap


def move_to_front(preferred: str, values: Iterable[str]):
    result: List[str] = []

    has_preferred = False
    for value in values:
        if value == preferred:
            has_preferred = True
        else:
            result.append(value)

    if has_preferred:
        result.insert(0, preferred)

    return result


def _list_ext():
    return move_to_front(".cpp", sorted(_fileext.keys()))


def _as_mustache(basename: str):
    name, ext = os.path.splitext(basename)
    return ext == ".mustache" and name or None


def _enum_licenses():
    root = os.path.abspath(os.path.join(package_root, template_dir, "licenses"))
    for _, dirnames, filenames in os.walk(root):
        dirnames[:] = []
        iter = filter(lambda x: x is not None, map(_as_mustache, filenames))
        return move_to_front("MIT", iter)
    return []


def _filter(
    src: Callable[[SettingsType], StrOrBool], flt: Callable[[StrOrBool], StrOrBool]
):
    def impl(settings: SettingsType):
        return flt(src(settings))

    return impl


def _get_nothing(_: SettingsType) -> StrOrBool:
    return ""


def _map(internal_key: str):
    def impl(key: str):
        mapped = internals.get(internal_key)
        if not isinstance(mapped, dict):
            return None
        return mapped.get(key)

    return impl


def _get_key(key: str):
    def impl(settings: SettingsType):
        return settings.get(key, "")

    return impl


_filters: Dict[str, Callable[[StrOrBool], StrOrBool]] = {
    "safe": lambda value: value.replace("-", "_"),
    "upper": lambda value: value.upper(),
    "lower": lambda value: value.lower(),
    "header": lambda cxx_ext: _fileext.get(cxx_ext, ".hpp"),
}


def _build_fixup(settings: SettingsType, fixup: str):
    fixup_refs = fixup.split("{")
    result = fixup_refs.pop(0)
    for ref_expr in fixup_refs:
        ref_text, verbose = ref_expr.split("}")
        filter_path = ref_text.split("$")

        ref = filter_path.pop(0)
        code = _get_nothing if ref == "" else _get_key(ref)

        for filter_name in filter_path:
            flt = _filters.get(filter_name)
            if flt is None:
                if filter_name.startswith("map:"):
                    internal_key = filter_name[4:]
                    code = _filter(code, _map(internal_key))
                continue
            code = _filter(code, flt)

        value = code(settings)

        if result:
            result += value
        else:
            result = value

        if verbose:
            result += verbose

    return result


def _fixup(settings: SettingsType, key: str, fixup: str, force=False):
    value = settings.get(key, "")
    if value != "" and not force:
        return

    value = _build_fixup(settings, fixup)
    settings[key] = value


def _fixed(fixup: str):
    def wrap(settings: SettingsType):
        return _build_fixup(settings, fixup)

    return wrap


def _get_default(setting: Setting, settings: SettingsType):
    value = setting.calc_value(settings)
    if isinstance(value, list):
        return value[0]
    return value


def all_default():
    settings: SettingsType = {}

    for setting in defaults:
        value = _get_default(setting, settings)
        settings[setting.json_key] = value

    for setting in switches:
        value = _get_default(setting, settings)
        settings[setting.json_key] = value

    return settings


def fixup(settings: SettingsType):
    for setting in hidden:
        value = _get_default(setting, settings)
        if isinstance(value, bool) or value != "":
            settings[setting.json_key] = value

    for coll in [defaults, hidden]:
        for setting in coll:
            _fixup(settings, setting.json_key, setting.fix or "", setting.force_fix)
    del settings["EXT"]

    result = {}
    for key in settings:
        path = key.split(".")
        ctx = result
        for step in path[:-1]:
            if step not in ctx or not isinstance(ctx[step], dict):
                ctx[step] = {}
            ctx = ctx[step]
        ctx[path[-1]] = settings[key]
    return result


def register_init_setting(*setting: Setting, is_hidden=False):
    (hidden if is_hidden else defaults).extend(setting)


def register_switch(key: str, prompt: str, enabled: bool):
    switches.append(Setting(key, prompt, value=enabled))


def register_internal(key: str, value: any):
    internals[key] = value


def get_internal(key: str, value: any = None):
    return internals.get(key, value)


internals = {}

switches: List[Setting] = []

defaults: List[Setting] = [
    Setting(
        "PROJECT.NAME",
        "Project name",
        lambda: os.path.basename(os.path.abspath("")) or "?project-name?",
    ),
    Setting("PROJECT.DESCRIPTION", "Project description"),
    Setting(
        "PROJECT.EMAIL",
        "Valid email, e.g. for CODE_OF_CONDUCT",
        _git_config("user.email"),
    ),
    Setting(
        "COPY.YEAR",
        "Year for copyright notices",
        str(datetime.date.today().year),
    ),
    Setting(
        "COPY.HOLDER",
        "Holder of the copyright",
        _git_config("user.name"),
    ),
    Setting("COPY.LICENSE", "License", _enum_licenses),
    Setting(
        "INCLUDE_PREFIX",
        'Prefix for includes (as in #include "{PREFIX}/version.hpp")',
        _fixed("{PROJECT.NAME}"),
    ),
    Setting(
        "NAME_PREFIX",
        "CMake variable name prefix",
        _fixed("{PROJECT.NAME$safe$upper}"),
    ),
    Setting(
        "NAMESPACE",
        "C++ namespace for the project",
        _fixed("{PROJECT.NAME$safe}"),
    ),
    Setting("EXT", "Extension for code files", _list_ext),
    Setting("SRCDIR", "Directory for code files", "src"),
    Setting(
        "INCLUDEDIR",
        "Directory for include files",
        "include",
        "{INCLUDEDIR}/{INCLUDE_PREFIX}",
        force_fix=True,
    ),
]

hidden: List[Setting] = [
    Setting("EXT.cxx", fix="{EXT}"),
    Setting("EXT.hxx", fix="{EXT.cxx$header}"),
]
