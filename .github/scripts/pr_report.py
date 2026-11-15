# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
Summarize the results of the Tests workflow as a Markdown PR comment.

Usage: ``python pr_report.py <artifacts-dir> <pyproject.toml>``

The artifacts directory holds one subdirectory per artifact, as downloaded
by ``actions/download-artifact`` without a ``name``:

- ``test-results-<os>-py<version>/`` with ``test-results.xml`` (JUnit) and
  ``coverage.xml`` (Cobertura),
- ``docstrings/interrogate.txt``,
- ``package/package.json`` with the outcome of each packaging step,
- ``dists/`` with the built distributions.

Results of the jobs themselves come from the ``TESTS_RESULT``,
``DOCSTRINGS_RESULT`` and ``PACKAGE_RESULT`` environment variables, and the
link to the run from the standard ``GITHUB_*`` ones.
"""

import json
import os
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

#: Hidden marker, by which the comment is found and updated on later runs.
MARKER = "<!-- proj-flow-checks -->"

#: Configuration, whose coverage is reported (same as in the job summary).
COVERAGE_FROM = ("ubuntu-latest", "3.12")

#: How many failed tests to list by name.
MAX_FAILURES = 15

ICON = {
    "success": "✅",
    "failure": "❌",
    "cancelled": "⏹️",
    "skipped": "⏭️",
}


def icon(result: str | None) -> str:
    return ICON.get(result or "", "❔")


@dataclass
class TestRun:
    os: str
    python: str
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    time: float = 0.0
    failed: list[str] = field(default_factory=list)

    @property
    def passed(self):
        return self.tests - self.failures - self.errors - self.skipped

    @property
    def broken(self):
        return self.failures + self.errors


def read_junit(path: Path, os_name: str, python: str) -> TestRun:
    run = TestRun(os_name, python)
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.iter("testsuite")
    for suite in suites:
        run.tests += int(suite.get("tests", 0))
        run.failures += int(suite.get("failures", 0))
        run.errors += int(suite.get("errors", 0))
        run.skipped += int(suite.get("skipped", 0))
        run.time += float(suite.get("time", 0))
        for case in suite.iter("testcase"):
            if case.find("failure") is not None or case.find("error") is not None:
                name = f"{case.get('classname', '')}::{case.get('name', '')}"
                run.failed.append(name.strip(":"))
    return run


def coverage_percent(path: Path) -> float | None:
    """Total of lines and branches, the same as ``coverage report`` shows."""
    root = ET.parse(path).getroot()
    try:
        valid = int(root.get("lines-valid", 0)) + int(root.get("branches-valid", 0))
        covered = int(root.get("lines-covered", 0)) + int(
            root.get("branches-covered", 0)
        )
    except ValueError:
        return None
    return 100.0 * covered / valid if valid else None


def interrogate_percent(path: Path) -> float | None:
    match = re.search(r"actual:\s*([0-9.]+)%", path.read_text(encoding="UTF-8"))
    return float(match.group(1)) if match else None


def floors(pyproject: Path) -> tuple[float | None, float | None]:
    try:
        tool = tomllib.loads(pyproject.read_text(encoding="UTF-8")).get("tool", {})
    except (OSError, tomllib.TOMLDecodeError):
        return None, None
    cov = tool.get("coverage", {}).get("report", {}).get("fail_under")
    doc = tool.get("interrogate", {}).get("fail-under")
    return cov, doc


def percent_cell(
    value: float | None, floor: float | None, result: str | None = None
) -> str:
    if value is None:
        return f"{icon(result)} no data"
    mark = "✅" if floor is None or value >= floor else "❌"
    floor_text = f" (minimum {floor:g}%)" if floor is not None else ""
    return f"{mark} {value:.1f}%{floor_text}"


def test_runs(artifacts: Path):
    runs: list[TestRun] = []
    coverage = None
    for directory in sorted(artifacts.glob("test-results-*")):
        match = re.fullmatch(r"test-results-(.+)-py(.+)", directory.name)
        if not match:
            continue
        os_name, python = match.groups()
        junit = directory / "test-results.xml"
        if junit.is_file():
            runs.append(read_junit(junit, os_name, python))
        cov = directory / "coverage.xml"
        if (os_name, python) == COVERAGE_FROM and cov.is_file():
            coverage = coverage_percent(cov)
    return runs, coverage


def tests_cell(result: str | None, runs: list[TestRun]) -> str:
    if not runs:
        return f"{icon(result)} no results"

    def configurations(count: int):
        return f"{count} configuration{'' if count == 1 else 's'}"

    # the same tests run everywhere, so count them once, not per run
    tests = max(run.tests for run in runs)
    text = f"{icon(result)} {tests} tests on {configurations(len(runs))}"

    failing = [run for run in runs if run.broken]
    if failing:
        failed = len({name for run in failing for name in run.failed})
        text += f", **{failed} failed on {configurations(len(failing))}**"

    skipped = max(run.skipped for run in runs)
    if skipped:
        text += f", up to {skipped} skipped"
    return text


def package_cell(result: str | None, artifacts: Path) -> tuple[str, list[str]]:
    report_path = artifacts / "package" / "package.json"
    try:
        steps: dict[str, str] = json.loads(report_path.read_text(encoding="UTF-8"))
    except (OSError, json.JSONDecodeError):
        steps = {}

    dists = sorted(p.name for p in (artifacts / "dists").glob("*") if p.is_file())
    details = [f"{icon(outcome)} {name}" for name, outcome in steps.items()]
    summary = f"{icon(result)} " + (", ".join(f"`{d}`" for d in dists) or "no packages")
    return summary, details


def build_report(artifacts: Path, pyproject: Path, env=os.environ) -> str:
    tests_result = env.get("TESTS_RESULT")
    docs_result = env.get("DOCSTRINGS_RESULT")
    package_result = env.get("PACKAGE_RESULT")

    cov_floor, doc_floor = floors(pyproject)
    runs, coverage = test_runs(artifacts)
    interrogate = artifacts / "docstrings" / "interrogate.txt"
    docstrings = interrogate_percent(interrogate) if interrogate.is_file() else None
    package, package_steps = package_cell(package_result, artifacts)

    results = [tests_result, docs_result, package_result]
    all_good = all(result == "success" for result in results)
    if all_good and coverage is not None and cov_floor is not None:
        all_good = coverage >= cov_floor

    sha = env.get("PR_HEAD_SHA") or env.get("GITHUB_SHA", "")
    server = env.get("GITHUB_SERVER_URL", "https://github.com")
    repo = env.get("GITHUB_REPOSITORY", "")
    run_id = env.get("GITHUB_RUN_ID", "")
    run_url = f"{server}/{repo}/actions/runs/{run_id}" if repo and run_id else ""

    title = "Checks passed" if all_good else "Checks need attention"
    lines = [MARKER, f"## {'✅' if all_good else '❌'} {title}", ""]
    if sha:
        about = f"for {sha[:7]}"
        if run_url:
            about += f" · [workflow run]({run_url})"
        lines.extend([about, ""])

    lines.extend(
        [
            "| Check | Result |",
            "|---|---|",
            f"| Tests | {tests_cell(tests_result, runs)} |",
            f"| Coverage | {percent_cell(coverage, cov_floor, tests_result)} |",
            f"| Docstrings | {percent_cell(docstrings, doc_floor, docs_result)} |",
            f"| Package | {package} |",
            "",
        ]
    )

    failed = sorted({name for run in runs for name in run.failed})
    if failed:
        lines.extend(["### Failed tests", ""])
        lines.extend(f"- `{name}`" for name in failed[:MAX_FAILURES])
        if len(failed) > MAX_FAILURES:
            lines.append(f"- … and {len(failed) - MAX_FAILURES} more")
        lines.append("")

    if runs:
        lines.extend(
            [
                "<details><summary>Tests per configuration</summary>",
                "",
                "| OS | Python | Passed | Failed | Skipped | Time |",
                "|---|---|--:|--:|--:|--:|",
            ]
        )
        for run in sorted(runs, key=lambda r: (r.os, r.python)):
            lines.append(
                f"| {run.os} | {run.python} | {run.passed} | {run.broken} "
                f"| {run.skipped} | {run.time:.1f}s |"
            )
        lines.extend(["", "</details>", ""])

    if package_steps:
        lines.extend(
            [
                "<details><summary>Package steps</summary>",
                "",
                *(f"- {step}" for step in package_steps),
                "",
                "</details>",
                "",
            ]
        )

    return "\n".join(lines)


def main():
    if len(sys.argv) != 3:
        print(__doc__.strip().split("\n\n")[1], file=sys.stderr)
        return 2
    # the report is redirected to a file; do not depend on the console code page
    sys.stdout.reconfigure(encoding="UTF-8")  # type: ignore[union-attr]
    print(build_report(Path(sys.argv[1]), Path(sys.argv[2])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
