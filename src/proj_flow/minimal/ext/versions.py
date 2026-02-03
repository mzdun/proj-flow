# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.ext.versions** update version schema files from version-updates
"""

from pathlib import Path
from typing import cast

from proj_flow.api import env
from proj_flow.log import release


@release.version_updaters.add
class VersionUpdater(release.VersionUpdater):
    def on_version_change_tags(
        self, rt: env.Runtime, new_version: str, tags: list[str]
    ) -> release.OneOrMoreStrings | None:
        if not tags:
            return None
        prev_tag = tags[-1]
        old_version = prev_tag[1:] if prev_tag.startswith("v") else prev_tag

        files = cast(dict[str, str], rt._cfg.get("version-updates", {}))
        changed_files: list[str] = []

        rt.message("Config")
        for key, value in files.items():
            if "$VERSION" not in value:
                continue

            path = Path(key)
            previous = value.replace("$VERSION", old_version)
            next = value.replace("$VERSION", new_version)
            rt.message(f"  >> {key} :: {previous} -> {next}")

            try:
                content = path.read_text(encoding="UTF-8")
            except FileNotFoundError:
                rt.fatal(f"File not found: {key}")

            new_content = content.replace(previous, next)
            if new_content != content:
                path.write_text(new_content, encoding="UTF-8")
                changed_files.append(key)

        return changed_files
