"""Tests for ``proj_flow.api.makefile``: ordering and up-to-date checks."""

import os
from pathlib import Path
from typing import List

import pytest
from fakes import FakeRuntime

from proj_flow.api.makefile import CyclicDependencyError, Makefile, Rule, Statement


class Touch(Rule):
    """Rule with a command line: ``touch <outputs>``."""

    def command(self, statement: Statement) -> List[str]:
        return ["touch", *statement.outputs]


class Direct(Rule):
    """Rule doing the work in :meth:`run`, recording the runtimes it got."""

    def __init__(self):
        self.runs: list = []

    def command(self, statement: Statement) -> List[str]:
        return []

    def run(self, statement: Statement, rt) -> None:
        self.runs.append(rt)
        if not rt.dry_run:
            for out in statement.outputs:
                Path(out).touch()


def _direct(outputs: List[str], inputs: List[str]):
    rule = Direct()
    return Statement(rule, outputs, inputs), rule


def _file(path: Path, mtime: float) -> str:
    path.touch()
    os.utime(path, (mtime, mtime))
    return str(path)


def _runtime(dry_run: bool = False) -> FakeRuntime:
    return FakeRuntime(dry_run=dry_run)


# ---------------------------------------------------------------- _needed


def test_missing_output_is_built(tmp_path):
    src = _file(tmp_path / "a.in", 100)
    st = Touch.statement([str(tmp_path / "a.out")], [src])
    rt = _runtime()

    assert st.run(rt)
    assert rt.calls == [("touch", str(tmp_path / "a.out"))]


def test_one_missing_output_of_many_is_built(tmp_path):
    src = _file(tmp_path / "a.in", 100)
    present = _file(tmp_path / "a.out", 200)
    st = Touch.statement([present, str(tmp_path / "b.out")], [src])

    assert st.run(_runtime())


def test_fresh_outputs_are_skipped(tmp_path):
    src = _file(tmp_path / "a.in", 100)
    dep = _file(tmp_path / "a.h", 100)
    out = _file(tmp_path / "a.out", 200)
    st = Touch.statement([out], [src], [dep])
    rt = _runtime()

    assert not st.run(rt)
    assert rt.calls == []


def test_newer_input_rebuilds(tmp_path):
    src = _file(tmp_path / "a.in", 300)
    out = _file(tmp_path / "a.out", 200)

    assert Touch.statement([out], [src]).run(_runtime())


def test_newer_implicit_dep_rebuilds(tmp_path):
    src = _file(tmp_path / "a.in", 100)
    dep = _file(tmp_path / "a.h", 300)
    out = _file(tmp_path / "a.out", 200)

    assert Touch.statement([out], [src], [dep]).run(_runtime())


def test_oldest_output_decides(tmp_path):
    src = _file(tmp_path / "a.in", 200)
    old = _file(tmp_path / "a.out", 150)
    new = _file(tmp_path / "b.out", 250)

    assert Touch.statement([old, new], [src]).run(_runtime())


def test_missing_dependency_rebuilds(tmp_path):
    out = _file(tmp_path / "a.out", 200)
    st = Touch.statement([out], [str(tmp_path / "gone.in")])

    assert st.run(_runtime())


def test_rebuilt_dependency_rebuilds_regardless_of_timestamps(tmp_path):
    src = _file(tmp_path / "a.in", 100)
    out = _file(tmp_path / "a.out", 200)
    st = Touch.statement([out], [src])

    assert not st.run(_runtime(), set())
    assert st.run(_runtime(), {src})


# ---------------------------------------------------------------- dry run


def test_dry_run_prints_instead_of_running(tmp_path):
    src = _file(tmp_path / "a.in", 300)
    out = _file(tmp_path / "a.out", 200)
    rt = _runtime(dry_run=True)

    assert Touch.statement([out], [src]).run(rt)
    assert rt.calls == []


def test_dry_run_skips_fresh_outputs(tmp_path):
    src = _file(tmp_path / "a.in", 100)
    out = _file(tmp_path / "a.out", 200)

    assert not Touch.statement([out], [src]).run(_runtime(dry_run=True))


def test_direct_rule_runs_with_the_runtime(tmp_path):
    src = _file(tmp_path / "a.in", 100)
    out = tmp_path / "a.out"
    st, rule = _direct([str(out)], [src])
    rt = _runtime()

    assert st.run(rt)
    assert rule.runs == [rt]
    assert out.exists()


def test_direct_rule_in_dry_run_gets_a_dry_copy(tmp_path):
    src = _file(tmp_path / "a.in", 100)
    out = tmp_path / "a.out"
    st, rule = _direct([str(out)], [src])
    rt = _runtime(dry_run=True)

    assert st.run(rt)
    (got,) = rule.runs
    assert got is not rt
    assert got.dry_run
    assert not out.exists()


def test_direct_rule_skips_fresh_outputs(tmp_path):
    src = _file(tmp_path / "a.in", 100)
    out = _file(tmp_path / "a.out", 200)
    st, rule = _direct([out], [src])

    assert not st.run(_runtime())
    assert rule.runs == []


# ---------------------------------------------------------------- Makefile


def test_statements_are_sorted_by_dependencies():
    link = Touch.statement(["app"], ["a.o", "b.o"])
    a = Touch.statement(["a.o"], ["a.c"])
    b = Touch.statement(["b.o"], ["b.c"], ["a.o"])

    assert Makefile([link, b, a]).statements == [a, b, link]


def test_cycle_is_reported():
    a = Touch.statement(["a"], ["b"])
    b = Touch.statement(["b"], ["a"])
    c = Touch.statement(["c"], ["x"])

    with pytest.raises(CyclicDependencyError) as err:
        Makefile([a, b, c])
    assert err.value.outputs == ["a", "b"]


def test_rebuild_propagates_down_the_chain(tmp_path):
    # a.in is newer than a.o; a.o is older than app, so only the first
    # statement is stale by timestamps, but app must follow
    src = _file(tmp_path / "a.in", 300)
    obj = _file(tmp_path / "a.o", 200)
    app = _file(tmp_path / "app", 250)
    rt = _runtime()

    Makefile(
        [Touch.statement([app], [obj]), Touch.statement([obj], [src])]
    ).run(rt)

    assert rt.calls == [("touch", obj), ("touch", app)]


def test_rebuild_propagates_in_dry_run(tmp_path):
    src = _file(tmp_path / "a.in", 300)
    obj = _file(tmp_path / "a.o", 200)
    app = _file(tmp_path / "app", 250)
    copy, rule = _direct([app], [obj])

    Makefile([copy, Touch.statement([obj], [src])]).run(_runtime(dry_run=True))

    assert len(rule.runs) == 1


def test_nothing_to_do(tmp_path, capsys):
    src = _file(tmp_path / "a.in", 100)
    out = _file(tmp_path / "a.out", 200)
    rt = _runtime()

    Makefile([Touch.statement([out], [src])]).run(rt)

    assert rt.calls == []
    assert "Nothing to do" in capsys.readouterr().err


def test_something_to_do_is_quiet(tmp_path, capsys):
    src = _file(tmp_path / "a.in", 100)
    rt = _runtime()

    Makefile([Touch.statement([str(tmp_path / "a.out")], [src])]).run(rt)

    assert rt.calls
    assert "Nothing to do" not in capsys.readouterr().err
