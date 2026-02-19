# Copyright (c) 2026 Marcin Zdun
# This file is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ctrf.ctrf** provides ctrf.io classes.
"""


import hashlib
from dataclasses import asdict, dataclass, field, fields
from typing import cast

from proj_flow import __version__


@dataclass
class Tool:
    name: str = field(default="proj_flow-ctrf")
    version: str = field(default=__version__)


@dataclass
class Summary:
    tests: int = field(default=0)
    passed: int = field(default=0)
    failed: int = field(default=0)
    skipped: int = field(default=0)
    pending: int = field(default=0)
    other: int = field(default=0)
    start: int | None = field(default=None)
    stop: int | None = field(default=None)

    def update(self, test: "Test"):
        self.update_start_stop(test)

        self.tests += 1
        for status in ["passed", "failed", "skipped", "pending", "other"]:
            if test.status == status:
                setattr(self, status, getattr(self, status) + 1)
                break

    def asdict(self):
        values = asdict(self)
        if self.start is None:
            values["start"] = 0
        if self.stop is None:
            values["stop"] = 0

        return values

    def update_start_stop(self, test: "Test"):
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
    name: str
    filePath: str | None
    line: int | None = field(default=None)
    suite: list[str] | None = field(default=None)
    status: str = field(default="pending")
    message: str | None = field(default=None)
    start: int | None = field(default=None)
    stop: int | None = field(default=None)
    timestamp: str | None = field(default=None)
    duration: int = field(default=0)

    def with_status(self, status: str, /, message: str | None = None):
        self.status = status
        self.message = message
        return self

    def __lt__(self, other):
        if not isinstance(other, Test):
            return False
        if self.filePath == self.filePath:
            return _less(self.line, self.line)
        return _less(self.filePath, other.filePath)

    def asdict(self):
        values = asdict(self)
        suite = self.suite or []
        values["name"] = " » ".join([*suite, self.name])
        values["id"] = _test_uuid(self)
        for f in fields(self):
            value = getattr(self, f.name)
            if value is None:
                del values[f.name]
        if "filePath" not in values and "line" in values:
            del values["line"]
        return values

    @staticmethod
    def from_dict(**kwargs):
        if "id" in kwargs:
            del kwargs["id"]
        return Test(**kwargs)


@dataclass
class Environment:
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
        values = asdict(self)
        for f in fields(self):
            value = getattr(self, f.name)
            if value is None:
                del values[f.name]
        return values

    def update(self, other):
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
        return Environment(**kwargs)


@dataclass
class Results:
    tool: Tool = field(default_factory=Tool)
    summary: Summary = field(default_factory=Summary)
    environment: Environment = field(default_factory=Environment)
    tests: list[Test] = field(default_factory=list)

    def update(self, test: Test):
        self.summary.update(test)
        self.tests.append(test)

    def asdict(self):
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
        return {
            "reportFormat": "CTRF",
            "specVersion": "0.0.0",
            "generatedBy": self.tool.name,
            "results": self.asdict(),
        }


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
