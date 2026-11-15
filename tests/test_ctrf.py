"""Tests for the CTRF report model in ``proj_flow.ctrf.ctrf``."""

import json
import re

from proj_flow.ctrf import ctrf

UUID5 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def test_summary_counts_statuses():
    summary = ctrf.Summary()
    for status in ["passed", "passed", "failed", "skipped", "pending", "weird"]:
        summary.update(ctrf.Test(name="t", status=status))

    assert summary.tests == 6
    assert summary.passed == 2
    assert summary.failed == 1
    assert summary.skipped == 1
    assert summary.pending == 1
    assert summary.other == 1


def test_summary_start_stop():
    summary = ctrf.Summary()
    assert summary.asdict()["start"] == 0
    assert summary.asdict()["stop"] == 0

    summary.update(ctrf.Test(name="a", start=20, stop=30))
    summary.update(ctrf.Test(name="b", start=10, stop=25))
    summary.update(ctrf.Test(name="c"))

    assert (summary.start, summary.stop) == (10, 30)


def test_recalc_name():
    test = ctrf.Test(name="case", suite=["outer", "inner"]).recalc_name()
    assert test.name == "outer » inner » case"
    assert ctrf.Test(name="case").recalc_name().name == "case"


def test_asdict_skips_none_and_generates_stable_id():
    test = ctrf.Test(name="case", line=12, suite=["s"])
    values = test.asdict()

    # line without a file path is dropped
    assert "line" not in values
    assert "filePath" not in values
    assert "message" not in values
    assert UUID5.match(values["id"])

    other = ctrf.Test(name="case", suite=["s"])
    assert other.asdict()["id"] == values["id"]
    assert ctrf.Test(name="case", suite=["t"]).asdict()["id"] != values["id"]


def test_from_dict_drops_id():
    test = ctrf.Test.from_dict(name="x", id="ignored", status="passed")
    assert test.id is None
    assert test.status == "passed"


def test_ordering_by_file_then_line():
    tests = [
        ctrf.Test(name="c", filePath="b.py", line=1),
        ctrf.Test(name="b", filePath="a.py", line=20),
        ctrf.Test(name="a", filePath="a.py", line=3),
        ctrf.Test(name="d"),
    ]
    assert [t.name for t in sorted(tests)] == ["d", "a", "b", "c"]
    assert not (tests[0] < "string")


def test_fold_output():
    test = ctrf.Test(name="x", message="failed", stdout=["a", "b"], stderr=["c"])
    test.fold_output()
    assert test.message == "failed\n\nstdout: a\nb\n\nstderr: c"
    assert test.stdout is None and test.stderr is None

    empty = ctrf.Test(name="y")
    empty.fold_output()
    assert empty.message is None


def test_environment_update():
    env = ctrf.Environment(appName="app", branchName="main")
    env.update(ctrf.Environment(branchName="dev", commit="abc"))
    assert env.asdict() == {"appName": "app", "branchName": "dev", "commit": "abc"}

    env.update("not an environment")
    assert env.branchName == "dev"


def test_results_roundtrip(tmp_path):
    results = ctrf.Results()
    results.update(ctrf.Test(name="ok", status="passed", start=1, stop=2))
    results.update(ctrf.Test(name="bad", status="failed", stderr=["boom"]))
    results.fold_output()

    path = tmp_path / "out" / "report.json"
    results.store_root_element(path)

    data = json.loads(path.read_text(encoding="UTF-8"))
    assert data["reportFormat"] == "CTRF"
    assert "environment" not in data["results"]
    assert data["results"]["summary"]["tests"] == 2
    assert data["results"]["summary"]["failed"] == 1
    assert data["results"]["tests"][1]["message"] == "stderr: boom"
