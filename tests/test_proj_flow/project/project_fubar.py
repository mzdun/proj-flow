# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from proj_flow.api import ctx
from proj_flow.project import api


@api.project_type.add
class FubarProject(api.ProjectType):
    def __init__(self):
        super().__init__("Test Project", "foo-bar")
        self.register_init_setting(ctx.Setting("fubar.key", "Prompt"))
        self.register_switch("fubar.switch", "Prompt", enabled=False)
        self.register_internal("fubar.internal", [1, 2, 3, 4, 5])

    def get_extension_list(self, context: dict) -> list[str]:
        if context.get("no-exts"):
            return []
        return ["package.ext.extension-1", "package.ext.extension-2"]
