# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)
"""
The **proj_flow.ext.github.switches** provides GitHub-related switches for new
projects.
"""

from proj_flow.api import ctx

ctx.register_common_switch("with_github_actions", "Use Github Actions", True)
ctx.register_common_switch(
    "with_github_social", "Use Github ISSUE_TEMPLATE, CONTRIBUTING.md, etc.", True
)
