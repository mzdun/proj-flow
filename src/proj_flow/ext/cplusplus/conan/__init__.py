# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.cplusplus.conan** provides the ``"Conan"`` step.
"""

import os
import textwrap
from typing import List

from proj_flow.api import env, step
from proj_flow.project import cplusplus

from ._conan import conan_api

CONAN_DIR = "build/conan"
CONAN_PROFILE = "_profile-compiler"
CONAN_PROFILE_GEN = "_profile-build_type"


@step.register
class ConanConfig:
    """Configures the project for ``preset`` config using ``build_type`` config."""

    name = "Conan"
    runs_before = ["CMake"]

    def platform_dependencies(self):
        return ["conan"]

    def is_active(self, config: env.Config, rt: env.Runtime) -> int:
        return os.path.isfile("conanfile.txt") or os.path.isfile("conanfile.py")

    def directories_to_remove(self, _: env.Config) -> List[str]:
        return [CONAN_DIR]

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        api = conan_api()

        profile_gen = f"{CONAN_DIR}/{CONAN_PROFILE_GEN}-{config.preset}"
        if not rt.dry_run:
            os.makedirs(CONAN_DIR, exist_ok=True)
            with open(profile_gen, "w", encoding="UTF-8") as profile:
                print(
                    textwrap.dedent(
                        f"""\
                        include({CONAN_PROFILE})

                        [settings]"""
                    ),
                    file=profile,
                )

                for setting in [
                    *api.settings(config),
                    f"build_type={config.build_type}",
                ]:
                    print(setting, file=profile)

        if api.config(rt, CONAN_DIR, f"./{CONAN_DIR}/{CONAN_PROFILE}", profile_gen):
            return 1
        if not rt.dry_run and os.path.exists("CMakeUserPresets.json"):
            os.remove("CMakeUserPresets.json")
        return 0
