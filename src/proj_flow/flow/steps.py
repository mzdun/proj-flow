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
    """
    Step being sorted, with its own copies of the ordering lists, which can be
    modified during sorting.
    """

    #: Step being sorted.
    plugin: step.Step
    #: Name of the step.
    name: str
    #: Names of the steps, which must run before this one.
    runs_after: List[str]
    #: Names of the steps, which must run after this one.
    runs_before: List[str]

    @staticmethod
    def from_step(plugin: step.Step):
        """
        Create the sorting entry, copying the name and ordering lists of a
        step.

        :param plugin: step to sort
        :returns: new sorting entry
        """
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
    """
    Sort the registered steps into :attr:`cfg.steps
    <proj_flow.api.env.FlowConfig.steps>` and rebuild :attr:`cfg.aliases
    <proj_flow.api.env.FlowConfig.aliases>` from the ``entry`` config. Unknown
    steps are removed from the aliases (in place) and aliases left without any
    steps are removed from ``entry``.

    :param cfg: flow configuration to update
    """
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
