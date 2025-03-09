# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from proj_flow.api import env, init


def test_init_defaults():
    step = init.InitStep()
    assert step.priority() == 100
    assert not step.platform_dependencies()

    step.postprocess(env.Runtime(), {})
