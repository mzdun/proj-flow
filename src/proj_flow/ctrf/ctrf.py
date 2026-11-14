# Copyright (c) 2026 Marcin Zdun
# This file is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ctrf.ctrf** provides ctrf.io classes.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from proj_flow import __version__


@dataclass
class Tool:
    """
    Tool, which produced the CTRF report.
    """

    name: str = field(default="proj_flow-ctrf")
    version: str = field(default=__version__)


@dataclass
class Summary:
    """
    Aggregated counters of all tests in the report.
    """

    #: Number of all tests.
    tests: int = field(default=0)
    passed: int = field(default=0)
    failed: int = field(default=0)
    skipped: int = field(default=0)
    pending: int = field(default=0)
    other: int = field(default=0)
    #: Earliest start of any test, in milliseconds since the Unix epoch.
    start: int | None = field(default=None)
    #: Latest stop of any test, in milliseconds since the Unix epoch.
    stop: int | None = field(default=None)

    def update(self, test: "Test"):
        """
        Count the test in the summary: the total and the counter matching
        test's status. A status other than ``"passed"``, ``"failed"``,
        ``"skipped"`` or ``"pending"`` is counted as ``"other"``, so the
        counters always add up to the total. Start and stop are extended with
        :meth:`update_start_stop`.

        :param test: test to count
        """
        self.update_start_stop(test)

        self.tests += 1
        status = test.status
        if status not in ["passed", "failed", "skipped", "pending"]:
            status = "other"
        setattr(self, status, getattr(self, status) + 1)

    def asdict(self):
        """
        Convert the summary to a JSON-ready dictionary. Missing start and
        stop are reported as ``0``, as the CTRF schema requires both.

        :returns: dictionary with all the counters, start and stop
        """
        values = asdict(self)
        if self.start is None:
            values["start"] = 0
        if self.stop is None:
            values["stop"] = 0

        return values

    def update_start_stop(self, test: "Test"):
        """
        Extend the summary's time range, so that it covers the test's start
        and stop, where these are known.

        :param test: test, whose start and stop are taken into account
        """
        if test.start is not None:
            if self.start is None:
                self.start = test.start
            else:
                self.start = min(self.start, test.start)
        if test.stop is not None:
            if self.stop is None:
                self.stop = test.stop
            else:
                self.stop = max(self.stop, test.stop)


def _less[T: (str, int)](lhs: T | None, rhs: T | None) -> bool:
    if lhs is None:
        return rhs is not None
    if rhs is None:
        return False
    return lhs < rhs


@dataclass
class Test:
    """
    Single test entry of the CTRF report.
    """

    #: Name of the test; after :meth:`recalc_name`, prefixed with the suite
    #: names.
    name: str
    #: Path of the file with the test, in POSIX notation.
    filePath: str | None = field(default=None)
    #: Line in :attr:`filePath`, where the test is defined.
    line: int | None = field(default=None)
    #: Names of the suites containing the test, outermost first.
    suite: list[str] | None = field(default=None)
    #: One of ``"passed"``, ``"failed"``, ``"skipped"``, ``"pending"`` or
    #: ``"other"``.
    status: str = field(default="pending")
    #: Failure or skip message.
    message: str | None = field(default=None)
    #: Start of the test, in milliseconds since the Unix epoch.
    start: int | None = field(default=None)
    #: End of the test, in milliseconds since the Unix epoch.
    stop: int | None = field(default=None)
    timestamp: str | None = field(default=None)
    #: Duration of the test, in milliseconds.
    duration: int = field(default=0)
    #: Lines of the standard output.
    stdout: list[str] | None = field(default=None)
    #: Lines of the standard error.
    stderr: list[str] | None = field(default=None)
    #: UUID of the test; when missing, :meth:`asdict` computes it from the
    #: name, suite and file path.
    id: str | None = field(default=None)

    def recalc_name(self):
        """
        Prefix the name with the suite names, joined with ``" » "``.

        :returns: this test, for chaining
        """
        suite = self.suite or []
        self.name = " » ".join([*suite, self.name])
        return self

    def with_status(self, status: str, /, message: str | None = None):
        """
        Set the status and the message of the test.

        :param status: new status of the test
        :param message: new message; replaces the previous one, even if
            ``None``
        :returns: this test, for chaining
        """
        self.status = status
        self.message = message
        return self

    def __lt__(self, other):
        if not isinstance(other, Test):
            return False
        if self.filePath == other.filePath:
            return _less(self.line, other.line)
        return _less(self.filePath, other.filePath)

    def asdict(self):
        """
        Convert the test to a JSON-ready dictionary, skipping all fields set
        to ``None``. The line is skipped also, if there is no file path. If
        the test has no ID yet, it is generated and stored in the test.

        :returns: dictionary with the fields of the test
        """
        if self.id is None:
            self.id = _test_uuid(self)
        values = asdict(self)
        for f in fields(self):
            value = getattr(self, f.name)
            if value is None:
                del values[f.name]
        if "filePath" not in values and "line" in values:
            del values["line"]
        return values

    def fold_output(self):
        """
        Move the standard output and standard error into the message, each
        as a ``stdout:``/``stderr:`` section separated by an empty line,
        and clear both output fields.
        """
        message = self.message or ""
        if self.stdout:
            if message:
                message += "\n\n"
            message += f"stdout: {'\n'.join(self.stdout)}"
            self.stdout = None
        if self.stderr:
            if message:
                message += "\n\n"
            message += f"stderr: {'\n'.join(self.stderr)}"
            self.stderr = None
        # keep a missing message missing, instead of reporting an empty one
        self.message = message or self.message

    @staticmethod
    def from_dict(**kwargs):
        """
        Create a test from the fields read from a CTRF report. Any ``id`` is
        dropped, so it can be regenerated by :meth:`asdict`.

        :param kwargs: fields of the test, as found in the report
        :returns: new test
        """
        if "id" in kwargs:
            del kwargs["id"]
        return Test(**kwargs)


@dataclass
class Environment:
    """
    Information about the environment, in which the tests were run. Fields
    set to ``None`` are left out of the report.
    """

    reportName: str | None = field(default=None)
    appName: str | None = field(default=None)
    appVersion: str | None = field(default=None)
    buildId: str | None = field(default=None)
    buildName: str | None = field(default=None)
    buildNumber: str | None = field(default=None)
    buildUrl: str | None = field(default=None)
    repositoryName: str | None = field(default=None)
    repositoryUrl: str | None = field(default=None)
    commit: str | None = field(default=None)
    branchName: str | None = field(default=None)
    osPlatform: str | None = field(default=None)
    osRelease: str | None = field(default=None)
    osVersion: str | None = field(default=None)
    testEnvironment: str | None = field(default=None)
    healthy: bool | None = field(default=None)

    def asdict(self):
        """
        Convert the environment to a JSON-ready dictionary, skipping all
        fields set to ``None``.

        :returns: dictionary with the known fields of the environment
        """
        values = asdict(self)
        for f in fields(self):
            value = getattr(self, f.name)
            if value is None:
                del values[f.name]
        return values

    def update(self, other):
        """
        Merge another environment into this one. Fields known in the other
        environment overwrite the fields of this one, fields set to ``None``
        there are left untouched. Does nothing, if ``other`` is not an
        :class:`Environment`.

        :param other: environment to merge into this one
        """
        if not isinstance(other, Environment):
            return

        merge = self.asdict()
        merge.update(other.asdict())
        for f in fields(self):
            if f.name not in merge:
                setattr(self, f.name, None)
            else:
                setattr(self, f.name, merge[f.name])

    @staticmethod
    def from_dict(**kwargs):
        """
        Create an environment from the fields read from a CTRF report.

        :param kwargs: fields of the environment, as found in the report
        :returns: new environment
        """
        return Environment(**kwargs)


@dataclass
class Results:
    """
    Results of a test run, as stored in the ``results`` property of the CTRF
    report.
    """

    tool: Tool = field(default_factory=Tool)
    summary: Summary = field(default_factory=Summary)
    environment: Environment = field(default_factory=Environment)
    tests: list[Test] = field(default_factory=list)

    def update(self, test: Test):
        """
        Add the test to the results and count it in the summary.

        :param test: test to add
        """
        self.summary.update(test)
        self.tests.append(test)

    def asdict(self):
        """
        Convert the results to a JSON-ready dictionary. The environment is
        skipped, if none of its fields are known.

        :returns: dictionary with the tool, environment, summary and tests
        """
        environment = self.environment.asdict()
        results = {
            "tool": asdict(self.tool),
            "environment": environment,
            "summary": self.summary.asdict(),
            "tests": [test.asdict() for test in self.tests],
        }

        if not len(environment.keys()):
            del results["environment"]

        return results

    def root_element(self):
        """
        Wrap the results into the top-level CTRF document.

        :returns: dictionary with the format, spec version, generator name
            and the results
        """
        return {
            "reportFormat": "CTRF",
            "specVersion": "0.0.0",
            "generatedBy": self.tool.name,
            "results": self.asdict(),
        }

    def fold_output(self):
        """
        Move the output of each test into its message, see
        :meth:`Test.fold_output`.
        """
        for test in self.tests:
            test.fold_output()

    def store_root_element(self, path: Path):
        """
        Write the CTRF document to a JSON file, creating parent directories
        as needed.

        :param path: path of the JSON file
        """
        data = self.root_element()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(json.dumps(data, ensure_ascii=False, indent=2).encode())


CTRF_NAMESPACE = b"\x6b\xa7\xb8\x10\x9d\xad\x11\xd1\x80\xb4\x00\xc0\x4f\xd4\x30\xc8"


def _test_uuid(test: Test):
    suite_id = "/".join(test.suite) if test.suite else ""
    identifier = (
        f"{test.name}|{suite_id}|{test.filePath if test.filePath else ''}".encode()
    )
    digest = hashlib.sha1(CTRF_NAMESPACE + identifier).hexdigest()
    return "-".join(
        [
            digest[0:8],
            digest[8:12],
            "5" + digest[13:16],  # Version 5
            f"{(int(digest[16:17], 16) & 0x3) | 0x8:x}" + digest[17:20],  # Variant bits
            digest[20:32],
        ]
    )
