# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.api.init** exposes APIs used by initialization extensions.
"""

from typing import List

from proj_flow.api.env import Runtime


class InitStep:
    """
    Step of ``proj-flow init``, run after the project files are written from
    the templates. Register an instance with :func:`register_init_step`.
    """

    def priority(self) -> int:
        """
        Order of the step; steps with lower priority run first. Steps with
        equal priority run in the order of registration.

        :returns: priority of the step, ``100`` by default
        """
        return 100

    def platform_dependencies(self) -> List[str]:
        """
        Tools this step needs, checked before the project is created. See
        :meth:`Step.platform_dependencies()
        <proj_flow.api.step.Step.platform_dependencies>` for the format.

        :returns: list of required tools
        """
        return []

    def postprocess(self, rt: Runtime, context: dict) -> None:
        """
        Finish the new project, e.g. by running tools in its directory.

        :param rt: runtime of the ``init`` command
        :param context: values used to fill the project templates
        """
        pass


__steps: List[InitStep] = []


def register_init_step(step: InitStep):
    """
    Add a step to be run by ``proj-flow init``.

    :param step: the step to register
    """
    global __steps
    __steps.append(step)
