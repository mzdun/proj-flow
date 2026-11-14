# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.test_runner.utils.counters** counts the test outcomes and prints the
per-test reports and the final summary.
"""

from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from proj_flow.ctrf import ctrf
from proj_flow.ext.test_runner.driver.test import Test


class color:
    """
    ANSI escape sequences used to color the test runner output.
    """

    #: Restores default terminal colors.
    reset = "\033[m"
    #: Progress counter, e.g. ``[ 3/42]``.
    counter = "\033[2;49;92m"
    #: Test name.
    name = "\033[0;49;90m"
    failed = "\033[0;49;91m"
    passed = "\033[2;49;92m"
    #: Skipped and saved tests.
    skipped = "\033[0;49;34m"


class TaskResult:
    """
    Possible outcomes of a single test run.
    """

    #: Test passed.
    OK = 0
    #: Test did not produce a result, e.g. a ``prepare`` or ``cleanup``
    #: command failed.
    SKIPPED = 1
    #: Expected output or files were missing and got stored instead of being
    #: checked; reported as skipped.
    SAVED = 2
    #: Output or files differ from expected ones.
    FAILED = 3
    #: Test case uses an unknown check; the message holds its name.
    CLIP_FAILED = 4


@dataclass
class ReportTestInfo:
    """
    Outcome and timing of a single test run, passed from a worker to
    :class:`Counters`.
    """

    test: Test
    #: Colored progress counter and test name, used as line prefix.
    test_id: str
    #: One of the :class:`TaskResult` values.
    outcome: int = field(default=0)
    #: Failure report or, for :attr:`TaskResult.CLIP_FAILED`, the name of
    #: unknown check.
    message: str | None = field(default=None)
    #: Start of the test, in milliseconds since the epoch.
    start: int = field(default=0)
    #: End of the test, in milliseconds since the epoch.
    stop: int = field(default=0)

    def with_outcome(self, outcome: int, message: str | None = None):
        """
        Sets the outcome and the message of this test.

        :param outcome: one of the :class:`TaskResult` values
        :param message: optional failure report
        :returns: this object
        """
        self.outcome = outcome
        self.message = message
        return self

    def get(self, top_level_suite: str, src_dir: Path):
        """
        Creates the CTRF entry for this test, without status. Test name is
        split on ``" :: "``, with the last part becoming the name and the
        rest becoming the suite under the top-level one.

        :param top_level_suite: name of the outermost suite
        :param src_dir: directory, against which test file path is made
            relative
        :returns: new CTRF test entry
        """
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
    """
    Accumulates outcomes of all tests, both as counters for the summary and
    as the CTRF results.
    """

    #: Name of the top-level suite, the tested target.
    suite: str
    #: Project source directory, base for test file paths in the report.
    src_dir: Path
    #: Number of failed tests.
    error_counter: int = field(default=0)
    #: Number of skipped tests, including the saved ones.
    skip_counter: int = field(default=0)
    #: Number of tests, which stored their expected results.
    save_counter: int = field(default=0)
    #: Lines for failed tests, repeated at the end of the summary.
    echo: list[str] = field(default_factory=list)
    results: ctrf.Results = field(default_factory=ctrf.Results)

    def report(self, info: ReportTestInfo):
        """
        Prints the outcome of a single test, updates the counters and adds
        the test to CTRF results.

        :param info: outcome of the test
        """
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
        self.echo.append(msg)
        self.results.update(result.with_status("failed", message=info.message))
        self.error_counter += 1

    def summary(self, counter: int):
        """
        Prints the number of failed and skipped tests, followed by the list
        of failed tests.

        :param counter: total number of tests
        :returns: ``True``, if no test failed
        """
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
