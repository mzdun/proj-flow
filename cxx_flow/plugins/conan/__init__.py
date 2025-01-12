# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
import textwrap
from typing import List

from cxx_flow.flow import ctx
from cxx_flow.flow.config import Config, Runtime
from cxx_flow.flow.step import Step, register_step

from ._conan import conan_api

CONAN_DIR = "build/conan"
CONAN_PROFILE = "_profile-compiler"
CONAN_PROFILE_GEN = "_profile-build_type"


class ConanConfig(Step):
    name = "Conan"

    def platform_dependencies(self):
        return ["conan"]

    def is_active(self, config: Config, rt: Runtime) -> int:
        return os.path.isfile("conanfile.txt") or os.path.isfile("conanfile.py")

    def directories_to_remove(self, _: Config) -> List[str]:
        return [CONAN_DIR]

    def run(self, config: Config, rt: Runtime) -> int:
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

        api.config(rt, CONAN_DIR, f"./{CONAN_DIR}/{CONAN_PROFILE}", profile_gen)
        if not rt.dry_run and os.path.exists("CMakeUserPresets.json"):
            os.remove("CMakeUserPresets.json")


register_step(ConanConfig())
ctx.register_switch("with_conan", "Use Conan for dependency manager", True)
