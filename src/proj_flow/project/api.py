# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.project.api** defines an extension point for project suites.
"""

from abc import ABC, abstractmethod
from typing import Any, List, NamedTuple, Optional

from proj_flow import base
from proj_flow.api import ctx, env
from proj_flow.project import interact


class ProjectType(ABC):
    name: str
    id: str

    def __init__(self, name: str, id: str):
        self.name = name
        self.id = id

    def register_switch(self, key: str, prompt: str, enabled: bool):
        ctx.register_switch(key, prompt, enabled, self.id)

    def register_internal(self, key: str, value: Any):
        ctx.register_internal(key, value)

    def register_init_setting(self, *settings: ctx.Setting, is_hidden=False):
        ctx.register_init_setting(*settings, is_hidden=is_hidden, project=self.id)

    def get_context(self, interactive: bool, rt: env.Runtime):
        return interact.get_context(interactive, self.id, rt)


project_type = base.registry.Registry[ProjectType]("ProjectType")


class ProjectNotFound(Exception):
    name: str

    def __init__(self, name: str):
        self.name = name


def get_project_type(id: str):
    result, _ = project_type.find(lambda proj: proj.id == id)
    if result is None:
        raise ProjectNotFound(id)
    return result
