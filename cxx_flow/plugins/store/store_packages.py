# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
import shutil
from typing import List, cast

from cxx_flow.api import env, step
from cxx_flow.base.uname import uname

from ..cmake.parser import get_project

_system, _version, _arch = uname()
_version = "" if _version is None else f"-{_version}"
_project_pkg = None


def _package_name(config: env.Config, pkg: str, group: str):
    debug = "-dbg" if config.build_type.lower() == "debug" else ""
    suffix = group and f"-{group}" or ""

    return f"{pkg}-{_system}{_version}-{_arch}{debug}{suffix}"


class StorePackages(step.Step):
    name = "StorePackages"
    runs_after = ["Pack"]

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        if not rt.dry_run:
            os.makedirs("build/artifacts", exist_ok=True)

        packages_dir = f"build/{config.preset}/packages"

        global _project_pkg
        if _project_pkg is None:
            _project_pkg = get_project("").pkg

        main_group = cast(List[str], rt._cfg.get("package", {}).get("main-group"))
        if main_group is not None and not rt.dry_run:
            src = _package_name(config, _project_pkg, main_group)
            dst = _package_name(config, _project_pkg, "")
            rt.print("mv", *(f"{package}.*" for package in (src, dst)), raw=True)
            for _, dirnames, filenames in os.walk(packages_dir):
                dirnames[:] = []
                extensions = [
                    filename[len(src) :]
                    for filename in filenames
                    if len(filename) > len(src)
                    and filename[: len(src)] == src
                    and filename[len(src)] == "."
                ]
            for extension in extensions:
                shutil.move(
                    f"{packages_dir}/{src}{extension}",
                    f"{packages_dir}/{dst}{extension}",
                )

        GITHUB_OUTPUT = os.environ.get("GITHUB_OUTPUT")
        if GITHUB_OUTPUT is not None:
            with open(GITHUB_OUTPUT, "a", encoding="UTF-8") as github_output:
                generators = ",".join(config.items.get("cpack_generator", []))
                print(f"CPACK_GENERATORS={generators}", file=github_output)

        return rt.cp(
            packages_dir,
            "build/artifacts/packages",
            f"^{_project_pkg}-.*$",
        )


step.register_step(StorePackages())
