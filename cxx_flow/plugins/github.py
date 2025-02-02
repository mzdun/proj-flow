# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)
"""
The **cxx_flow.plugins.github** provides GitHub-related switches for new
projects.
"""

from cxx_flow.api import ctx

ctx.register_switch("with_github_actions", "Use Github Actions", True)
ctx.register_switch(
    "with_github_social", "Use Github ISSUE_TEMPLATE, CONTRIBUTING.md, etc.", True
)
