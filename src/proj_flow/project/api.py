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
    """
    Kind of project ``proj-flow init`` can create, registered with
    :data:`project_type`.

    :param name: human-readable name of the project type
    :param id: identifier of the project type, as used by ``proj-flow init``
    """

    name: str
    id: str

    def __init__(self, name: str, id: str):
        self.name = name
        self.id = id

    def register_switch(self, key: str, prompt: str, enabled: bool):
        """
        Add a yes/no question asked only for this project type, after all the
        other settings.

        :param key: key of the flag in the context, e.g. ``with.cmake``
        :param prompt: question to ask
        :param enabled: default answer
        """
        ctx.register_switch(key, prompt, enabled, self.id)

    def register_internal(self, key: str, value: Any):
        """
        Store a value for the ``init`` machinery, which is not asked for, e.g.
        a mapping used by the ``$map:<key>`` filter of
        :attr:`Setting.fix <proj_flow.api.ctx.Setting.fix>`. Internal values are
        shared by all project types.

        :param key: name of the value
        :param value: the value
        """
        ctx.register_internal(key, value)

    def register_init_setting(self, *settings: ctx.Setting, is_hidden=False):
        """
        Add settings used only by this project type.

        :param settings: settings to add
        :param is_hidden: never ask for these settings, only calculate them
        """
        ctx.register_init_setting(*settings, is_hidden=is_hidden, project=self.id)

    def get_context(self, setup: interact.ContextSetup, rt: env.Runtime):
        """
        Build the mustache context for a new project of this type, asking for
        the settings and switches, unless the setup says otherwise.

        :param setup: how the answers are gathered
        :param rt: runtime used for messages
        :returns: the mustache context
        """
        return interact.get_context(setup, self.id, rt)

    def append_extensions(self, context: dict):
        """
        Prepend the ``extensions`` list returned by :meth:`get_extension_list`
        to ``.flow/config.yml`` in the current directory. Called by
        ``proj-flow init`` after the project files are written. Does nothing,
        if the list is empty.

        :param context: the mustache context of the new project
        """
        extensions = self.get_extension_list(context)
        if len(extensions) == 0:
            return
        text = "".join(f"\n  - {ext}" for ext in extensions)
        text = f"extensions:{text}\n\n"

        with open(".flow/config.yml", encoding="UTF-8") as config_file:
            content = config_file.read()

        with open(".flow/config.yml", "w", encoding="UTF-8") as config_file:
            config_file.write(text)
            config_file.write(content)

    @abstractmethod
    def get_extension_list(self, context: dict) -> List[str]:
        """
        List the *Project Flow* extensions the new project needs in its flow
        config, e.g. depending on the switches answered.

        :param context: the mustache context of the new project
        :returns: names of the extension modules
        """
        ...


#: Registry of the project types known to ``proj-flow init``.
project_type = base.registry.Registry[ProjectType]("ProjectType")


class ProjectNotFound(Exception):
    """
    No project type with given id is registered.

    :param name: id of the missing project type
    """

    name: str

    def __init__(self, name: str):
        self.name = name


def get_project_type(id: str):
    """
    Find a registered project type.

    :param id: identifier of the project type, e.g. ``cxx``
    :returns: the project type
    :raises ProjectNotFound: no project type has this id
    """
    result, _ = project_type.find(lambda proj: proj.id == id)
    if result is None:
        raise ProjectNotFound(id)
    return result


def load_common_init_setting_extensions():
    """
    Load the extensions registering ``proj-flow init`` settings and switches
    shared by all project types, i.e. the GitHub switches.
    """
    env.load_extensions(["proj_flow.ext.github.switches"])
