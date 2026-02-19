# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import concurrent.futures
import json
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Generator, Iterator

from proj_flow import __version__
from proj_flow.api import env
from proj_flow.ext.test_runner.driver.test import Env, Test
from proj_flow.ext.test_runner.utils.counters import (
    Counters,
    ReportTestInfo,
    TaskResult,
    color,
)


def _task(
    runtime: Env, tested: Test, current_counter: int
) -> tuple[ReportTestInfo, str]:
    env = runtime.with_random_temp_subdir()

    test_counter = f"{color.counter}[{current_counter:>{env.counter_digits}}/{env.counter_total}]{color.reset}"
    test_name = f"{color.name}{tested.name}{color.reset}"
    test_id = f"{test_counter} {test_name}"

    print(test_id)
    os.makedirs(env.tempdir, exist_ok=True)

    info = ReportTestInfo(tested, test_id)

    info.start = int(time.time() * 1000 + 0.5)
    result = tested.run(env)
    info.stop = int(time.time() * 1000 + 0.5)

    if result is None:
        return (info.with_outcome(TaskResult.SKIPPED), env.tempdir)

    actual, files = result
    reports: list[str] = []

    saved = False
    if tested.expected is None:
        tested.data["expected"] = actual.as_dict()
        tested.store()
        saved = True

    for file in files:
        fixed = file.patched(env, tested.cwd, tested.patches)

        if fixed.needs_saving:
            copied = fixed.copy_file()
            saved = saved or copied

        elif fixed.generated.content != fixed.template.content:
            reports.append(tested.report_file(fixed))

    if saved:
        return (info.with_outcome(TaskResult.SAVED), env.tempdir)

    clipped = tested.clip(actual)

    if isinstance(clipped, str):
        return (info.with_outcome(TaskResult.CLIP_FAILED, clipped), env.tempdir)

    if actual != tested.expected and clipped != tested.expected:
        reports.append(tested.report_io(actual))

    if reports:
        reports.append(tested.test_footer(env, env.tempdir))
        return (info.with_outcome(TaskResult.FAILED, "\n".join(reports)), env.tempdir)

    return (info.with_outcome(TaskResult.OK), env.tempdir)


def run_and_report_tests(
    independent_tests: list[tuple[Test, int]],
    linear_tests: list[tuple[Test, int]],
    install_dir: Path,
    env: Env,
    thread_count: int,
    rt: env.Runtime,
    ctrf: str | None,
    report_name: str | None,
):
    counters = Counters(env.target_name, env.source_dir())

    if independent_tests:
        _report_tests(counters, _run_async_tests(independent_tests, env, thread_count))

    _report_tests(counters, _run_sync_tests(linear_tests, env))

    shutil.rmtree(install_dir, ignore_errors=True)
    shutil.rmtree("build/.testing", ignore_errors=True)

    if ctrf:
        head = rt.capture("git", "rev-parse", "--abbrev-ref", "HEAD", silent=True)
        environment = counters.results.environment
        environment.reportName = report_name
        environment.appName = env.target_name
        environment.appVersion = env.version
        if head.returncode == 0:
            environment.branchName = head.stdout.strip()

        counters.results.store_root_element(Path(ctrf))

    if not counters.summary(len(independent_tests) + len(linear_tests)):
        return 1

    return 0


def _run_async_tests(tests: list[tuple[Test, int]], env: Env, thread_count: int):
    with concurrent.futures.ThreadPoolExecutor(thread_count) as executor:
        futures: list[concurrent.futures.Future[tuple[ReportTestInfo, str]]] = []
        for test, counter in tests:
            futures.append(executor.submit(_task, env, test, counter))

        for future in concurrent.futures.as_completed(futures):
            yield future.result()


def _run_sync_tests(tests: list[tuple[Test, int]], env: Env):
    for test, counter in tests:
        yield _task(env, test, counter)


def _report_tests(
    counters: Counters,
    results: Iterator[tuple[ReportTestInfo, str]],
):
    for info, tempdir in results:
        counters.report(info)
        shutil.rmtree(tempdir, ignore_errors=True)
