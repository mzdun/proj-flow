# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
from typing import List

from proj_flow.api import env, step

from ..capture import Capture


class DefaultStep(step.Step):
    @property
    def name(self) -> str:
        return "Default"

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        return 0


class PropStep1(step.PropContainerStep):
    def __init__(self):
        super().__init__(name="PropA", runs_after=["A", "B", "C"], runs_before=["E"])

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        return 0


class PropStep2(step.PropContainerStep):
    def __init__(self):
        super().__init__(name="PropB", runs_after=["A", "B", "D"], runs_before=["Z"])

    def is_active(self, _config: env.Config, _rt: env.Runtime) -> bool:
        return False

    def run(self, _config: env.Config, _rt: env.Runtime) -> int:
        return 1


class SerialStep(step.SerialStep):
    @property
    def name(self) -> str:
        return "Serial"

    def __init__(self, children: List[step.Step] | None = None):
        super().__init__()
        self.children = children or []


def test_init_defaults():
    rt = env.Runtime()
    cfg = env.Config({}, [])

    default = DefaultStep()
    prop_a = PropStep1()
    prop_b = PropStep2()

    serial = SerialStep([default, prop_a])

    assert not default.runs_after
    assert not default.runs_before
    assert not default.platform_dependencies()
    assert default.is_active(cfg, rt)
    assert not default.directories_to_remove(cfg)

    assert prop_a.runs_after == ["A", "B", "C"]
    assert prop_a.runs_before == ["E"]
    assert not prop_a.platform_dependencies()
    assert prop_a.is_active(cfg, rt)
    assert not prop_a.directories_to_remove(cfg)
    assert prop_a.run(cfg, rt) == 0

    assert prop_b.runs_after == ["A", "B", "D"]
    assert prop_b.runs_before == ["Z"]
    assert not prop_b.platform_dependencies()
    assert not prop_b.is_active(cfg, rt)
    assert not prop_b.directories_to_remove(cfg)
    assert prop_b.run(cfg, rt) == 1

    assert serial.runs_after == ["A", "B", "C"]
    assert serial.runs_before == ["E"]
    assert not serial.platform_dependencies()
    assert serial.is_active(cfg, rt)
    assert not serial.directories_to_remove(cfg)
    assert serial.run(cfg, rt) == 0

    serial.children = [prop_a, prop_b]

    assert serial.runs_after == ["A", "B", "C", "D"]
    assert serial.runs_before == ["E", "Z"]
    assert not serial.platform_dependencies()
    assert not serial.is_active(cfg, rt)
    assert not serial.directories_to_remove(cfg)
    assert serial.run(cfg, rt) == 1


def test_init_registrar():
    step.__steps = []
    step.register()(DefaultStep)
    step.register(PropStep1)
    step.register(PropStep2)
    step.register(SerialStep)

    with Capture() as capture:
        step.verbose_info()

    assert capture.stderr == ""
    assert (
        capture.stdout == ""
        '-- Step: adding "Default" from `test_proj_flow.api.test_step.DefaultStep`\n'
        '-- Step: adding "PropA" from `test_proj_flow.api.test_step.PropStep1`\n'
        '-- Step: adding "PropB" from `test_proj_flow.api.test_step.PropStep2`\n'
        '-- Step: adding "Serial" from `test_proj_flow.api.test_step.SerialStep`\n'
    )

    os.environ["READTHEDOCS"] = "1"
    name_error_raised = False
    try:
        step.register(DefaultStep)
        name_error_raised = False
    except NameError:
        name_error_raised = True
    assert not name_error_raised

    del os.environ["READTHEDOCS"]
    name_error_raised = False
    try:
        step.register(DefaultStep)
        name_error_raised = False
    except NameError:
        name_error_raised = True
    assert name_error_raised
