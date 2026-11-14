# Copyright (c) 2026 Marcin Zdun
# This file is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ctrf.junit** allows conversion from XML JUnit files
to JSON ctrf.io files.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from dateutil import tz

from proj_flow.ctrf import ctrf


def read_junit_testcase(
    suite: list[str],
    element: ET.Element,
    source_dir: Path,
):
    """
    Convert a single ``<testcase>`` element to a CTRF test. Google Test's
    ``value_param`` is appended to the name in parentheses, ``file`` is made
    relative to the source directory and ``time`` (in seconds) becomes the
    duration in milliseconds. A ``timestamp`` (local time, unless it names
    the time zone) becomes the start of the test, and the start plus the
    duration becomes its stop. The test fails, if it has any ``<failure>``
    children, otherwise is skipped, if it has any ``<skipped>`` children,
    otherwise it passes. Messages of these children become the message of
    the test, ``<system-out>`` and ``<system-err>`` become its output.

    :param suite: names of the suites containing the test, outermost first
    :param element: the ``<testcase>`` element
    :param source_dir: directory, against which test file path is made
        relative
    :returns: new CTRF test, or ``None``, if the test case has no name, no
        time, or a ``status`` other than ``run``
    """
    attrib = element.attrib

    name = attrib.get("name")
    value_param = attrib.get("value_param")
    time_str = attrib.get("time")
    timestamp_str = attrib.get("timestamp")
    file = attrib.get("file")
    line_str = attrib.get("line")
    if (attrib.get("status") not in [None, "run"]) or not name or not time_str:
        return None

    timestamp: int | None = None
    if timestamp_str:
        try:
            test_start = datetime.fromisoformat(timestamp_str)
            if test_start.tzinfo is None:
                # Google Test writes the local time, without the time zone
                test_start = test_start.replace(tzinfo=tz.tzlocal())
            epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
            timestamp = int((test_start - epoch).total_seconds() * 1000 + 0.5)
        except (ValueError, OverflowError, OSError):
            # malformed, or too close to the epoch for the local time zone
            # on some platforms
            timestamp = None

        if timestamp is not None and timestamp < (24 * 60 * 60 * 1000):
            timestamp = None

    if value_param:
        value_param = f" ({value_param})"
    else:
        value_param = ""

    test = ctrf.Test(
        name=f"{name}{value_param}",
        filePath=(
            Path(file).relative_to(source_dir, walk_up=True).as_posix()
            if file
            else None
        ),
        suite=suite,
    ).recalc_name()

    try:
        test.line = int(line_str) if line_str is not None else None
    except ValueError:
        test.line = None

    try:
        test.duration = int(float(time_str) * 1000 + 0.5) if time_str is not None else 0
    except ValueError:
        test.duration = 0

    if timestamp is not None:
        test.start = timestamp
        test.stop = timestamp + test.duration

    failures: list[str] = []
    skips: list[str] = []
    stdout: list[str] = []
    stderr: list[str] = []
    for child in element:
        if child.tag == "failure":
            failures.extend(child.attrib.get("message", "").split("\n"))
            continue
        if child.tag == "skipped":
            skips.extend(child.attrib.get("message", "").split("\n"))
            continue
        if child.tag == "system-out":
            stdout.extend((child.text or "").split("\n"))
            continue
        if child.tag == "system-err":
            stderr.extend((child.text or "").split("\n"))
            continue

    test.status = "passed"
    if failures:
        test.message = "\n".join(failures)
        test.status = "failed"
    elif skips:
        test.message = "\n".join(skips)
        test.status = "skipped"

    if stdout:
        test.stdout = stdout
    if stderr:
        test.stderr = stderr

    return test


def read_junit_testsuite(
    ctrf: ctrf.Results,
    testsuite_group: str,
    source_dir: Path,
    testsuite: ET.Element,
):
    """
    Add all ``<testcase>`` children of a ``<testsuite>`` element to the
    results. The tests are placed in two suites: the group and the name of
    the test suite. Test suites without a name are ignored.

    :param ctrf: results to add the tests to
    :param testsuite_group: name of the outermost suite
    :param source_dir: directory, against which test file paths are made
        relative
    :param testsuite: the ``<testsuite>`` element
    """
    testsuite_name = testsuite.attrib.get("name")
    if not testsuite_name:
        return

    suite = [testsuite_group, testsuite_name]
    for testcase in testsuite:
        if testcase.tag != "testcase":
            continue
        test = read_junit_testcase(suite, testcase, source_dir)
        if test:
            ctrf.update(test)


def read_junit_testsuites(
    ctrf: ctrf.Results, testsuite_group: str, filename: Path, source_dir: Path
):
    """
    Read a JUnit XML file and add its tests to the results. The root element
    is either a single ``<testsuite>`` (e.g. from Qt QTest), or a
    ``<testsuites>`` element, whose children are read as test suites (e.g.
    from Google Test).

    :param ctrf: results to add the tests to
    :param testsuite_group: name of the outermost suite
    :param filename: path of the JUnit XML file
    :param source_dir: directory, against which test file paths are made
        relative
    """
    tree = ET.parse(filename)
    root = tree.getroot()
    if root.tag == "testsuite":
        read_junit_testsuite(ctrf, testsuite_group, source_dir, root)
        return

    for testsuite in root:
        read_junit_testsuite(ctrf, testsuite_group, source_dir, testsuite)
