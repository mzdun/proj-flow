# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import importlib
import os
from dataclasses import dataclass
from types import ModuleType
from typing import List, Union

from . import step
from .config import FlowConfig, RunAlias


@dataclass
class Sorted:
    plugin: step.Step
    name: str
    runs_after: List[str]

    @staticmethod
    def from_step(plugin: step.Step):
        name = plugin.name
        runs_after = [*plugin.runs_after]
        return Sorted(plugin, name, runs_after)


def _load_plugins(directory: str, package: Union[str, None]):
    for _, dirnames, filenames in os.walk(directory):
        for dirname in dirnames:
            importlib.import_module(f".{dirname}", package=package)
        for filename in filenames:
            if filename == "__init__.py":
                continue
            importlib.import_module(
                f".{os.path.splitext(filename)[0]}", package=package
            )
        dirnames[:] = []
        pass


def _load_module_plugins(cfg: FlowConfig, mod: ModuleType):
    spec = mod.__spec__
    if not spec:
        return
    for location in spec.submodule_search_locations:
        _load_plugins(location, spec.name)


def _sort_steps():
    steps = step.__steps
    unsorted = [Sorted.from_step(step) for step in steps]
    known_names = [step.name for step in unsorted]

    for plugin in unsorted:
        runs_after: List[str] = []
        for name in plugin.runs_after:
            if name in known_names:
                runs_after.append(name)
        plugin.runs_after = runs_after

    result: List[step.Step] = []

    while len(unsorted) > 0:
        layer = [plugin for plugin in unsorted if len(plugin.runs_after) == 0]
        unsorted = [plugin for plugin in unsorted if len(plugin.runs_after) > 0]
        for plugin in layer:
            for remaining in unsorted:
                try:
                    remaining.runs_after.remove(plugin.name)
                except ValueError:
                    pass
        result.extend(plugin.plugin for plugin in layer)
        if len(layer) == 0:
            result.extend(plugin.plugin for plugin in unsorted)
            break

    return result


def load_steps(cfg: FlowConfig):
    std_plugins = importlib.import_module("cxx_flow.plugins")
    _load_module_plugins(cfg, std_plugins)
    # TODO: use cfg.steps.plugins

    return _sort_steps()


def clean_aliases(cfg: FlowConfig, valid_steps: List[step.Step]):
    entries = cfg._cfg.get("entry")
    if not entries:
        return

    step_names = {step.name for step in valid_steps}

    keys_to_remove: List[str] = []
    for key in entries:
        entry = entries[key]
        steps = entry.get("steps")
        if not steps:
            keys_to_remove.append(key)
            continue
        rewritten: List[str] = []
        for step in steps:
            if step in step_names:
                rewritten.append(step)
        steps[:] = rewritten

        if not steps:
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del entries[key]

    cfg.steps = valid_steps
    cfg.aliases = [RunAlias.from_json(key, entries[key]) for key in entries]
