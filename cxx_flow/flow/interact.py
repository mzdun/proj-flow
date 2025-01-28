# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from dataclasses import dataclass
from typing import List, Union

from prompt_toolkit import prompt as tk_prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.validation import Validator

from cxx_flow.api import ctx


@dataclass
class Eval:
    key: str
    prompt: str
    value: ctx.Values

    @classmethod
    def load_default(cls, default: ctx.Setting, previous: ctx.SettingsType):
        value = default.calc_value(previous)
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

    def _ps(self, default: ctx.Values, counter: int, size: int):
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
        defaults: Union[bool | List[str]],
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


def prompt():
    settings: ctx.SettingsType = {}

    size = len(ctx.defaults) + len(ctx.switches)
    counter = 1

    for setting in ctx.defaults:
        loaded = Eval.load_default(setting, settings)
        value = loaded.interact(counter, size)
        settings[loaded.key] = value
        counter += 1

    for setting in ctx.switches:
        loaded = Eval.load_default(setting, settings)
        value = loaded.interact(counter, size)
        settings[loaded.key] = value
        counter += 1

    return settings
