# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **cxx_flow.plugins.store** provides ``"StoreTests"`` step.
"""

from cxx_flow.api import env, step


@step.register
class StoreTests(step.Step):
    """Stores test results gathered during tests for ``preset`` config value."""

    name = "StoreTests"
    runs_after = ["Test"]

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        return rt.cp(
            f"build/{config.preset}/test-results", "build/artifacts/test-results"
        )
