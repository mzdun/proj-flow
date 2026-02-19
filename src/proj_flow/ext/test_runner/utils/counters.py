# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from proj_flow.ctrf import ctrf
from proj_flow.ext.test_runner.driver.test import Test


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
class ReportTestInfo:
    test: Test
    test_id: str
    outcome: int = field(default=0)
    message: str | None = field(default=None)
    start: int = field(default=0)
    stop: int = field(default=0)

    def with_outcome(self, outcome: int, message: str | None = None):
        self.outcome = outcome
        self.message = message
        return self

    def get(self, top_level_suite: str, src_dir: Path):
        suite = self.test.name.split(" :: ")
        name = suite[-1]
        suite = suite[:-1]
        suite.insert(0, top_level_suite)
        filename = self.test.filename.relative_to(src_dir, walk_up=True)
        return ctrf.Test(
            name=name,
            filePath=filename.as_posix(),
            suite=suite,
            message=self.message,
            start=self.start,
            stop=self.stop,
        ).recalc_name()


@dataclass
class Counters:
    suite: str
    src_dir: Path
    error_counter: int = field(default=0)
    skip_counter: int = field(default=0)
    save_counter: int = field(default=0)
    echo: list[str] = field(default_factory=list)
    results: ctrf.Results = field(default_factory=ctrf.Results)

    def report(self, info: ReportTestInfo):
        result = info.get(self.suite, self.src_dir)
        if info.outcome == TaskResult.SKIPPED:
            print(f"{info.test_id} {color.skipped}SKIPPED{color.reset}")
            self.results.update(result.with_status("skipped"))
            self.skip_counter += 1
            return

        if info.outcome == TaskResult.SAVED:
            print(f"{info.test_id} {color.skipped}saved{color.reset}")
            self.results.update(result.with_status("skipped"))
            self.skip_counter += 1
            self.save_counter += 1
            return

        if info.outcome == TaskResult.CLIP_FAILED:
            msg = f"{info.test_id} {color.failed}FAILED (unknown check '{info.message}'){color.reset}"
            print(msg)
            self.echo.append(msg)
            self.results.update(
                result.with_status(
                    "failed", message=f"internal error: unknown check '{info.message}'"
                )
            )
            self.error_counter += 1
            return

        if info.outcome == TaskResult.OK:
            self.results.update(result.with_status("passed"))
            print(f"{info.test_id} {color.passed}PASSED{color.reset}")
            return

        if info.message is not None:
            print(info.message)

        msg = f"{info.test_id} {color.failed}FAILED{color.reset}"
        print(msg)
        result.status = "failed"
        self.echo.append(msg)
        self.results.update(result.with_status("failed", message=info.message))
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
