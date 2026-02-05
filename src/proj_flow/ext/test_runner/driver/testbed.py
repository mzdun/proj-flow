# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import concurrent.futures
import os
import shutil
from pathlib import Path
from typing import Any, Generator

from proj_flow.ext.test_runner.driver.test import Env, Test
from proj_flow.ext.test_runner.utils.counters import Counters, TaskResult, color


def _task(
    runtime: Env, tested: Test, current_counter: int
) -> tuple[int, str, str | None, str]:
    env = runtime.with_random_temp_subdir()

    test_counter = f"{color.counter}[{current_counter:>{env.counter_digits}}/{env.counter_total}]{color.reset}"
    test_name = f"{color.name}{tested.name}{color.reset}"
    test_id = f"{test_counter} {test_name}"

    print(test_id)
    os.makedirs(env.tempdir, exist_ok=True)

    result = tested.run(env)
    if result is None:
        return (TaskResult.SKIPPED, test_id, None, env.tempdir)

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
        return (TaskResult.SAVED, test_id, None, env.tempdir)

    clipped = tested.clip(actual)

    if isinstance(clipped, str):
        return (TaskResult.CLIP_FAILED, test_id, clipped, env.tempdir)

    if actual != tested.expected and clipped != tested.expected:
        reports.append(tested.report_io(actual))

    if reports:
        reports.append(tested.test_footer(env, env.tempdir))
        return (TaskResult.FAILED, test_id, "\n".join(reports), env.tempdir)

    return (TaskResult.OK, test_id, None, env.tempdir)


def run_and_report_tests(
    independent_tests: list[tuple[Test, int]],
    linear_tests: list[tuple[Test, int]],
    install_dir: Path,
    env: Env,
    thread_count: int,
):
    counters = Counters()

    if independent_tests:
        _report_tests(counters, _run_async_tests(independent_tests, env, thread_count))

    _report_tests(counters, _run_sync_tests(linear_tests, env))

    shutil.rmtree(install_dir, ignore_errors=True)
    shutil.rmtree("build/.testing", ignore_errors=True)

    if not counters.summary(len(independent_tests) + len(linear_tests)):
        return 1

    return 0


def _run_async_tests(tests: list[tuple[Test, int]], env: Env, thread_count: int):
    with concurrent.futures.ThreadPoolExecutor(thread_count) as executor:
        futures: list[concurrent.futures.Future[tuple[int, str, str | None, str]]] = []
        for test, counter in tests:
            futures.append(executor.submit(_task, env, test, counter))

        for future in concurrent.futures.as_completed(futures):
            yield future.result()


def _run_sync_tests(tests: list[tuple[Test, int]], env: Env):
    for test, counter in tests:
        yield _task(env, test, counter)


def _report_tests(
    counters: Counters,
    results: Generator[tuple[int, str, str | None, str], Any, None],
):
    for outcome, test_id, message, tempdir in results:
        counters.report(outcome, test_id, message)
        shutil.rmtree(tempdir, ignore_errors=True)
