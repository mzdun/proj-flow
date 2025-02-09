# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.project.interact** provides initialization context through
user prompts.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional, Union

from prompt_toolkit import prompt as tk_prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text.base import AnyFormattedText
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.validation import Validator

from proj_flow.api import ctx, env


@dataclass
class _Question:
    key: str
    prompt: str
    value: ctx.Values

    @classmethod
    def load_default(
        cls,
        default: ctx.Setting,
        previous: ctx.SettingsType,
        override: Optional[ctx.StrOrBool],
    ):
        value = default.calc_value(previous)
        if override is not None:
            if isinstance(value, (str, bool)) and type(value) == type(override):
                value = override
            elif isinstance(value, list) and isinstance(override, str):
                value = ctx.move_to_front(override, value)
        return cls(default.json_key, default.prompt, value)

    def interact(self, counter: int, size: int) -> ctx.StrOrBool:
        if isinstance(self.value, str):
            return self._get_str(self.value, counter, size)
        if isinstance(self.value, bool):
            return self._get_flag(self.value, counter, size)
        return self._get_list(self.value, counter, size)

    @property
    def ps(self):
        return self.prompt or f'"{self.key}"'

    def _ps(self, default: ctx.Values, counter: int, size: int) -> AnyFormattedText:
        if default:
            if isinstance(default, str):
                return [
                    ("", f"[{counter}/{size}] {self.ps} ["),
                    ("bold", default),
                    ("", f"]: "),
                ]
            if isinstance(default, bool):
                b = "bold"
                n = ""
                on_true = (b if default else n, "yes")
                on_false = (b if not default else n, "no")
                return [
                    ("", f"[{counter}/{size}] {self.ps} ["),
                    on_true,
                    ("", " / "),
                    on_false,
                    ("", f"]: "),
                ]
            return [
                ("", f"[{counter}/{size}] {self.ps} ["),
                ("bold", default[0]),
                ("", f"{''.join(f' / {x}' for x in default[1:])}]: "),
            ]
        return f"[{counter}/{size}] {self.ps}: "

    def _get_str(self, default: str, counter: int, size: int):
        value = tk_prompt(self._ps(default, counter, size))
        if not value:
            value = default
        return value

    def _get_flag(self, default: bool, counter: int, size: int):
        value = self._tk_prompt(
            default, ["yes", "no", "on", "off", "1", "0"], counter, size
        )
        result = default
        if value:
            result = value.lower() in ["1", "on", "y", "yes"]
        return result

    def _get_list(self, defaults: List[str], counter: int, size: int):
        value = self._tk_prompt(defaults, defaults, counter, size)
        if not value:
            value = defaults[0]
        return value

    def _tk_prompt(
        self,
        defaults: Union[bool, List[str]],
        words: List[str],
        counter: int,
        size: int,
    ):
        def valid(word: str):
            return word == "" or word in words

        validator = Validator.from_callable(valid)
        completer = WordCompleter(words)
        return tk_prompt(
            self._ps(defaults, counter, size),
            validator=validator,
            completer=completer,
            complete_while_typing=True,
            complete_style=CompleteStyle.READLINE_LIKE,
        )


def _project_filter(project: Optional[str]):
    if project is None:

        def impl(setting: ctx.Setting):
            return setting.project is None

        return impl

    def impl(setting: ctx.Setting):
        return setting.project is None or setting.project == project

    return impl


def _prompt(
    wanted: Callable[[ctx.Setting], bool], overrides: ctx.SettingsType
) -> ctx.SettingsType:
    settings: ctx.SettingsType = {}

    defaults = [setting for setting in ctx.defaults if wanted(setting)]
    switches = [setting for setting in ctx.switches if wanted(setting)]

    size = len(defaults) + len(switches)
    counter = 1

    for coll in [defaults, switches]:
        for setting in coll:
            loaded = _Question.load_default(
                setting, settings, overrides.get(setting.json_key)
            )
            value = loaded.interact(counter, size)
            settings[loaded.key] = value
            counter += 1

    return settings


def _all_default(wanted: Callable[[ctx.Setting], bool], overrides: ctx.SettingsType):
    """
    Chooses default answers for all details of newly-crated project.

    :returns: Dictionary with default values of all interactive settings
        and switches.
    """

    settings: ctx.SettingsType = {}

    defaults = [setting for setting in ctx.defaults if wanted(setting)]
    switches = [setting for setting in ctx.switches if wanted(setting)]

    for coll in [defaults, switches]:
        for setting in coll:
            if setting.json_key in overrides:
                settings[setting.json_key] = overrides[setting.json_key]
            else:
                value = _get_default(setting, settings)
                settings[setting.json_key] = value

    return settings


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


def _fixup_context(settings: ctx.SettingsType, wanted: Callable[[ctx.Setting], bool]):
    defaults = [setting for setting in ctx.defaults if wanted(setting)]
    hidden = [setting for setting in ctx.hidden if wanted(setting)]

    for setting in hidden:
        value = _get_default(setting, settings)
        if isinstance(value, bool) or value != "":
            settings[setting.json_key] = value

    for coll in [defaults, hidden]:
        for setting in coll:
            _fixup(settings, setting.json_key, setting.fix or "", setting.force_fix)

    try:
        del settings["EXT"]
    except KeyError:
        pass

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


def get_context(interactive: bool, project: Optional[str], rt: env.Runtime):
    """
    Prompts user to provide details of newly-crated project. If `interactive`
    is true, however, this functions skips the prompts and chooses all the
    default answers.

    :param interactive: Selects, if the initialization process is done through
        prompts, or not.

    :param project: Alows to select questions for any given language.

    :param rt: Runtime with config loaded in.

    :returns: Dictionary with answers to all interactive settings and switches.
    """

    overrides = rt._cfg.get("defaults", {})

    wanted = _project_filter(project)
    return _fixup_context(
        (
            _all_default(wanted, overrides)
            if not interactive
            else _prompt(wanted, overrides)
        ),
        wanted,
    )
