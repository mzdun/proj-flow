# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.tests.steps** provides the ``"GTestToCtrf"`` step.
"""

import json
from pathlib import Path
from typing import Any, List, cast

from proj_flow.api import env, step
from proj_flow.ctrf import ctrf
from proj_flow.ctrf.googletest import read_junit_testsuites


@step.register
class GTestToCtrf(step.Step):
    """Converts Google Test JUnit XML reports to CTRF JSON files."""

    @property
    def name(self) -> str:
        """:meta private:"""
        return "GTestToCtrf"

    @property
    def runs_after(self) -> List[str]:
        """:meta private:"""
        return ["Test"]

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        source_dir = rt.root
        build_dir = config.build_dir

        test_cg = cast(dict, rt.items.get("test", {}))
        gtest_dir = build_dir / cast(str, test_cg.get("gtest-dir", "test-results"))
        ctrf_dir = build_dir / cast(str, test_cg.get("ctrf-dir", "test-results"))

        paths: list[Path] = []
        if gtest_dir.is_dir():
            for cwd, _, files in gtest_dir.walk():
                paths.extend(cwd / file for file in files if file.endswith(".xml"))
        else:
            rt.message("Cannot find", str(gtest_dir))

        for path in paths:
            rt.message("Found", str(path))

        if rt.dry_run or not paths:
            return 0

        ctrf_dir.mkdir(parents=True, exist_ok=True)
        for filename in sorted(paths):
            results = ctrf.Results()
            read_junit_testsuites(results, filename.stem, filename, source_dir)

            results.tool.name = "gtest-to-ctrf"
            results.store_root_element(ctrf_dir / f"{filename.stem}.json")

        return 0


@step.register
class MergeCtrfFiles(step.Step):
    """Merge CTRF JSON files from single run to single file."""

    @property
    def name(self) -> str:
        """:meta private:"""
        return "MergeCtrfFiles"

    @property
    def runs_after(self) -> List[str]:
        """:meta private:"""
        return ["Test", "GTestToCtrf"]

    def run(self, config: env.Config, rt: env.Runtime) -> int:
        build_dir = config.build_dir

        test_cg = cast(dict, rt.items.get("test", {}))
        ctrf_dir = build_dir / cast(str, test_cg.get("ctrf-dir", "test-results"))
        output = build_dir / cast(str, test_cg.get("ctrf-report", "ctrf-tests.json"))

        paths: list[Path] = []
        if ctrf_dir.is_dir():
            for cwd, _, files in ctrf_dir.walk():
                paths.extend(cwd / file for file in files if file.endswith(".json"))
        else:
            rt.message("Cannot find", str(ctrf_dir))

        for path in paths:
            rt.message("Found", str(path))

        if rt.dry_run or not paths:
            return 0

        results = ctrf.Results()
        for path in sorted(paths):
            data = json.loads(path.read_bytes())
            results_data = cast(dict[str, dict], data.get("results", {}))
            tests_data = cast(list[dict[str, Any]], results_data.get("tests", []))
            for test_data in tests_data:
                test = ctrf.Test.from_dict(**test_data)
                results.update(test)
            environment_data = cast(dict[str, Any], results_data.get("environment", {}))
            new_env = ctrf.Environment.from_dict(**environment_data)
            results.environment.update(new_env)

        results.tool.name = "proj_flow-ctrf-merge"
        results.store_root_element(output)

        duration = 0
        summary = results.summary

        if summary.start is not None and summary.stop is not None:
            duration = summary.stop - summary.start

        duration_str = f"{duration} ms"
        if duration >= 1000:
            duration_str = f"{duration / 1000} s"

        log: list[tuple[str, str, str]] = [
            ("Total", str(summary.tests), ""),
            ("Passed", str(summary.passed), "\033[0;32m"),
            ("Failed", str(summary.failed), "\033[0;31m"),
            ("Pending", str(summary.pending), ""),
            ("Skipped", str(summary.skipped), "\033[0;33m"),
            ("Other", str(summary.other), ""),
            ("Duration", duration_str, ""),
        ]

        width = 0
        offset = 0
        for label, value, _ in log:
            if value == "0":
                continue
            width = max(width, len(label) + 1)
            offset = max(offset, len(value))

        for label, value, color in log:
            if value == "0":
                continue
            lab = f"{label}:"
            rt.message(
                f"  {color}{lab:<{width}} {value:>{offset}}\033[m", level=env.Msg.STATUS
            )

        return 0
