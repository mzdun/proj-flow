# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.ext.bug_report** adds next version to bug_report.yaml
next to CHANGELOG.rst.
"""

import re
import sys

from proj_flow.log import release

YAML_PATH = ".github/ISSUE_TEMPLATE/bug_report.yaml"


@release.version_updaters.add
class VersionUpdater(release.VersionUpdater):
    def on_version_change(self, new_version: str):
        with open(YAML_PATH, encoding="UTF-8") as inf:
            lines = inf.readlines()

        try:
            id_index = lines.index("  id: version\n")
            option_index = lines.index("    options:\n", id_index) + 1
            lines[option_index:option_index] = f"      - v{new_version}\n"
        except ValueError as e:
            print(e, file=sys.stderr)

        with open(YAML_PATH, "w", encoding="UTF-8") as outf:
            outf.writelines(lines)

        return YAML_PATH
