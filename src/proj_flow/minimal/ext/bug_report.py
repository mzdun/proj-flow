# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.ext.bug_report** adds next version to bug_report.yaml
next to CHANGELOG.rst.
"""

import re
import sys

from proj_flow.api import env
from proj_flow.log import release

YAML_PATH = ".github/ISSUE_TEMPLATE/bug_report.yaml"


def _version(ver: str) -> tuple[int, int, int, str]:
    if ver[:1] == "v":
        ver = ver[1:]

    m = re.match(r"([0-9]+)\.([0-9]+)\.([0-9]+)(.*)", ver)
    if m is None:
        print(f"fatal error: cannot parse {ver}", file=sys.stderr)
        raise SystemExit(1)
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), ver)


def _prev_version(new_version: str, tags: list[str]):
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
    def on_version_change_tags(
        self, rt: env.Runtime, new_version: str, tags: list[str]
    ):
        with open(YAML_PATH, encoding="UTF-8") as inf:
            lines = inf.readlines()

        id_index = -1
        option_index = -1
        option_index_end = -1
        options_indent: str | None = None

        for index, line in enumerate(lines):
            if line.endswith("id: version\n"):
                id_index = index
            elif id_index >= 0 and option_index == -1 and line.endswith("options:\n"):
                option_index = index + 1

        if option_index >= 0 and option_index + 1 < len(lines):
            pos = lines[option_index].find("- ")
            if pos >= 0:
                options_indent = lines[option_index][: pos + 2]

        if not options_indent:
            rt.message(
                f"fatal error: cannot find version options in {YAML_PATH}",
                level=env.Msg.ALWAYS,
            )
            return None

        removable = ["Current (v", "Previous (v", "Older, than v"]
        surviving_options = list[str]()
        for index in range(option_index, len(lines)):
            line = lines[index]
            if not line.startswith(options_indent):
                option_index_end = index
                break
            unindented = line[len(options_indent) :]
            if any(unindented.startswith(rem) for rem in removable):
                continue
            surviving_options.append(line)

        old_version = _prev_version(new_version, tags)

        version_range = [f"{options_indent}Current (v{new_version})\n"]
        if old_version:
            version_range.extend(
                [
                    f"{options_indent}Previous (v{old_version})\n",
                    f"{options_indent}Older, than v{old_version}\n",
                ]
            )
        version_range.extend(surviving_options)

        try:
            lines[option_index:option_index_end] = version_range
        except ValueError as e:
            print(e, file=sys.stderr)

        with open(YAML_PATH, "w", encoding="UTF-8") as outf:
            outf.writelines(lines)

        return YAML_PATH
