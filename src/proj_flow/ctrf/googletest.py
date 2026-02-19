# Copyright (c) 2026 Marcin Zdun
# This file is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ctrf.googletest** allows conversion from XML JUnit files
to JSON ctrf.io files.
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from dateutil import tz

from proj_flow.ctrf import ctrf


def read_junit_testcase(suite: list[str], element: ET.Element, source_dir: Path):
    attrib = element.attrib

    status = attrib.get("status")
    name = attrib.get("name")
    value_param = attrib.get("value_param")
    time_str = attrib.get("time")
    timestamp_str = attrib.get("timestamp")
    file = attrib.get("file")
    line_str = attrib.get("line")
    if status != "run" or not name or not time_str or not timestamp_str:
        return None

    local_dt_posing_as_utc = datetime.fromisoformat(timestamp_str)
    local_dt_posing_as_utc.replace(tzinfo=tz.tzlocal())
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    timestamp: int | None = int(
        (local_dt_posing_as_utc.astimezone(tz.tzutc()) - epoch).total_seconds() * 1000
        + 0.5
    )

    if timestamp < (24 * 60 * 60 * 1000):
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
        start=timestamp,
    )

    try:
        test.line = int(line_str) if line_str is not None else None
    except ValueError:
        test.line = None

    try:
        test.duration = int(float(time_str) * 1000 + 0.5) if time_str is not None else 0
    except ValueError:
        test.duration = 0

    if test.start is not None:
        test.stop = test.duration + test.start

    failures: list[str] = []
    is_skipped = False
    for child in element:
        if child.tag == "failure":
            failures.append(child.attrib.get("message", ""))
            continue
        if child.tag == "skipped":
            is_skipped = True
            continue

    test.status = "passed"
    if failures:
        test.message = "\n".join(failures)
        test.status = "failed"
    elif is_skipped:
        test.status = "skipped"

    return test


def read_junit_testsuites(
    ctrf: ctrf.Results, testuite_group: str, filename: Path, source_dir: Path
):
    tree = ET.parse(filename)
    root = tree.getroot()
    for testsuite in root:
        testsuite_name = testsuite.attrib.get("name")
        if not testsuite_name:
            continue

        suite = [testuite_group, testsuite_name]
        for testcase in testsuite:
            test = read_junit_testcase(suite, testcase, source_dir)
            if test:
                ctrf.update(test)
