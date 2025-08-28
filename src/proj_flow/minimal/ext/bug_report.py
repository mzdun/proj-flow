# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.ext.bug_report** adds next version to bug_report.yaml
next to CHANGELOG.rst.
"""

import re
import sys
from typing import List, Tuple

from proj_flow.log import release

YAML_PATH = ".github/ISSUE_TEMPLATE/bug_report.yaml"


def _version(ver: str) -> Tuple[int, int, int, str]:
    if ver[:1] == "v":
        ver = ver[1:]

    m = re.match(r"([0-9]+)\.([0-9]+)\.([0-9]+)(.*)", ver)
    if m is None:
        print(f"fatal error: cannot parse {ver}", file=sys.stderr)
        raise SystemExit(1)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), ver)


def _prev_version(new_version: str, tags: List[str]):
    current = _version(new_version)
    versions = [_version(tag) for tag in reversed(tags)]
    index = 0
    while index < len(versions):
        comp = versions[index]
        if comp[0] != current[0] or comp[1] != current[1]:
            break

        index += 1
    if index >= len(versions):
        index = 0

    return None if index > len(versions) else versions[index][-1]


@release.version_updaters.add
class VersionUpdater(release.VersionUpdater):
    def on_version_change_tags(self, new_version: str, tags: List[str]):
        old_version = _prev_version(new_version, tags)

        range = [f"      - Current (v{new_version})\n"]
        if old_version:
            range.extend(
                [
                    f"      - Previous (v{old_version})\n",
                    f"      - Older, than v{old_version}\n",
                ]
            )

        with open(YAML_PATH, encoding="UTF-8") as inf:
            lines = inf.readlines()

        try:
            id_index = lines.index("  id: version\n")
            option_index = lines.index("    options:\n", id_index) + 1
            option_index_end = option_index
            while option_index_end < len(lines) and lines[option_index_end].startswith(
                "      - "
            ):
                option_index_end += 1
            lines[option_index:option_index_end] = range
        except ValueError as e:
            print(e, file=sys.stderr)

        with open(YAML_PATH, "w", encoding="UTF-8") as outf:
            outf.writelines(lines)

        return YAML_PATH
