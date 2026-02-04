# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
import random
import string
from dataclasses import dataclass, field, replace

from proj_flow.ext.test_runner.driver.test import Env, Test, fix_file_write


class color:
    reset = "\033[m"
    counter = "\033[2;49;92m"
    name = "\033[0;49;90m"
    failed = "\033[0;49;91m"
    passed = "\033[2;49;92m"
    skipped = "\033[0;49;34m"


class TaskResult:
    OK = 0
    SKIPPED = 1
    SAVED = 2
    FAILED = 3
    CLIP_FAILED = 4


@dataclass
class Counters:
    error_counter: int = 0
    skip_counter: int = 0
    save_counter: int = 0
    echo: list[str] = field(default_factory=list)

    def report(self, outcome: int, test_id: str, message: str | None):
        if outcome == TaskResult.SKIPPED:
            print(f"{test_id} {color.skipped}SKIPPED{color.reset}")
            self.skip_counter += 1
            return

        if outcome == TaskResult.SAVED:
            print(f"{test_id} {color.skipped}saved{color.reset}")
            self.skip_counter += 1
            self.save_counter += 1
            return

        if outcome == TaskResult.CLIP_FAILED:
            msg = f"{test_id} {color.failed}FAILED (unknown check '{message}'){color.reset}"
            print(msg)
            self.echo.append(msg)
            self.error_counter += 1
            return

        if outcome == TaskResult.OK:
            print(f"{test_id} {color.passed}PASSED{color.reset}")
            return

        if message is not None:
            print(message)
        msg = f"{test_id} {color.failed}FAILED{color.reset}"
        print(msg)
        self.echo.append(msg)
        self.error_counter += 1

    def summary(self, counter: int):
        print(f"Failed {self.error_counter}/{counter}")
        if self.skip_counter > 0:
            skip_test = "test" if self.skip_counter == 1 else "tests"
            if self.save_counter > 0:
                print(
                    f"Skipped {self.skip_counter} {skip_test} (including {self.save_counter} due to saving)"
                )
            else:
                print(f"Skipped {self.skip_counter} {skip_test}")

        if len(self.echo):
            print()
        for echo in self.echo:
            print(echo)

        return self.error_counter == 0


def task(
    env1: Env, tested: Test, current_counter: int
) -> tuple[int, str, str | None, str]:
    temp_instance = "".join(random.choice(string.ascii_letters) for _ in range(16))
    tempdir = f"{env1.tempdir}/{temp_instance}"
    tempdir_alt = None

    if env1.tempdir_alt is not None:
        tempdir_alt = f"{env1.tempdir_alt}{os.sep}{temp_instance}"

    env2 = replace(env1, tempdir=tempdir, tempdir_alt=tempdir_alt)

    test_counter = f"{color.counter}[{current_counter:>{env2.counter_digits}}/{env2.counter_total}]{color.reset}"
    test_name = f"{color.name}{tested.name}{color.reset}"
    test_id = f"{test_counter} {test_name}"

    print(test_id)
    os.makedirs(tempdir, exist_ok=True)

    result = tested.run(env2)
    if result is None:
        return (TaskResult.SKIPPED, test_id, None, tempdir)

    actual, files = result
    reports: list[str] = []

    saved = False
    if tested.expected is None:
        tested.data["expected"] = actual.as_dict()
        tested.store()
        saved = True

    for file in files:
        fixed = fix_file_write(file, env2, tested.cwd, tested.patches)

        if fixed.needs_saving():
            copied = fixed.copy_file()
            saved = saved or copied

        elif fixed.generated.content != fixed.template.content:
            reports.append(tested.report_file(fixed))

    if saved:
        return (TaskResult.SAVED, test_id, None, tempdir)

    clipped = tested.clip(actual)

    if isinstance(clipped, str):
        return (TaskResult.CLIP_FAILED, test_id, clipped, tempdir)

    if actual != tested.expected and clipped != tested.expected:
        reports.append(tested.report_io(actual))

    if reports:
        reports.append(tested.test_footer(env2, tempdir))
        return (TaskResult.FAILED, test_id, "\n".join(reports), tempdir)

    return (TaskResult.OK, test_id, None, tempdir)
