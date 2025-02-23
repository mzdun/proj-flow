# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)
"""
The **proj_flow.ext.github.switches** provides GitHub-related switches for new
projects.
"""

from proj_flow.api import ctx

ctx.register_common_switch("with.github.actions", "Use Github Actions", True)
ctx.register_common_switch(
    "with.github.auto-release",
    "Make a GitHub release automatically on each closed PR",
    False,
)
ctx.register_common_switch(
    "with.github.social", "Use Github ISSUE_TEMPLATE, CONTRIBUTING.md, etc.", True
)

ctx.register_common_init_setting(
    ctx.Setting(
        "with.github.no-auto-release",
        value=lambda settings: not settings.get("with.github.auto-release"),
    ),
    is_hidden=True,
)
