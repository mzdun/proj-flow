# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.flow.steps** allows loading both predefined and project-specific
steps.
"""

from dataclasses import dataclass
from typing import List, cast

from proj_flow.api import env, step


@dataclass
class Sorted:
    plugin: step.Step
    name: str
    runs_after: List[str]
    runs_before: List[str]

    @staticmethod
    def from_step(plugin: step.Step):
        name = plugin.name
        runs_after = [*plugin.runs_after]
        runs_before = [*plugin.runs_before]
        return Sorted(plugin, name, runs_after, runs_before)


def _sort_steps():
    steps = step.__steps
    unsorted = [Sorted.from_step(step) for step in steps]
    known_names = [step.name for step in unsorted]

    for plugin in unsorted:
        for name in plugin.runs_before:
            for successor in unsorted:
                if successor.name != name:
                    continue
                successor.runs_after.append(plugin.name)
                break

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


def clean_aliases(cfg: env.FlowConfig):
    cfg_steps = _sort_steps()
    cfg.steps = cfg_steps

    entries = cfg.entry
    if not entries:
        return

    step_names = {step.name for step in cfg_steps}

    keys_to_remove: List[str] = []
    for key in entries:
        entry = entries[key]
        if isinstance(entry, dict):
            steps = cast(List[str], entry.get("steps", []))
        else:
            steps = cast(List[str], entry)
        if len(steps) == 0:
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

    cfg.aliases = [env.RunAlias.from_json(key, entries[key]) for key in entries]
