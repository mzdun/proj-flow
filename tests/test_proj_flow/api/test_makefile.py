# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import argparse
from dataclasses import dataclass

import pytest

from proj_flow.api import env, makefile

from ..load_flow_cfg import load_flow_cfg


@pytest.fixture
def flow_cfg(mocker):
    return load_flow_cfg(mocker, user_cfg=None, proj_cfg=None)


def _args(**kwargs):
    return argparse.Namespace(**kwargs)


@dataclass
class Exec:
    app: str
    args: list[str]


@dataclass
class Command:
    name: str
    inputs: list[str]
    outputs: list[str]
    implicit_deps: list[str]


Output = Exec | Command


class CustomRule(makefile.Rule):
    name: str
    target: list[Output]

    def __init__(self, name: str, target: list[Output]):
        super().__init__()
        self.name = name
        self.target = target

    def __repr__(self):
        return f'CustomRule("{self.name}")'

    def __str__(self):
        return f"rule::<{self.name}>"

    def command(self, _st: makefile.Statement) -> list[str]:
        return []

    def run(self, st: makefile.Statement, rt: env.Runtime):
        if not rt.dry_run:
            self.target.append(
                Command(
                    self.name,
                    inputs=st.inputs,
                    outputs=st.outputs,
                    implicit_deps=st.implicit_deps,
                )
            )
        return 0


class RunRule(makefile.Rule):
    tool: str = ""

    def __repr__(self):
        return f"Compile({self.tool})"

    def __str__(self):
        return f"rule::{self.tool}"

    def command(self, statement: makefile.Statement) -> list[str]:
        return [self.tool, *statement.inputs, "-o", *statement.outputs]


class CodeGen(RunRule):
    def __init__(self):
        super().__init__()
        self.tool = "code-gen"

    def __repr__(self):
        return "CodeGen()"


class Compile(RunRule):
    def __init__(self):
        super().__init__()
        self.tool = "compile"

    def __repr__(self):
        return "Compile()"


class Link(RunRule):
    def __init__(self):
        super().__init__()
        self.tool = "link"

    def __repr__(self):
        return "Link()"


def _mtime(files: dict[str, float]):
    def wrap(path: str):
        try:
            return files[path]
        except KeyError as exc:
            raise FileNotFoundError() from exc

    return wrap


def _log_call(target: list[Output]):
    def wrap(app: str, *args: str):
        target.append(Exec(app, list(args)))
        return 0

    return wrap


def _bad_call(target: list[Output]):
    def wrap(app: str, *args: str):
        target.append(Exec(app, list(args)))
        return 1

    return wrap


def test_run():
    pass


# pylint: disable-next=redefined-outer-name
def test_custom_rules(flow_cfg: env.FlowConfig, mocker):
    rt = env.Runtime.from_flow_cfg(flow_cfg)
    target: list[Output] = []

    code_gen = CustomRule("code_gen", target)
    comp = CustomRule("compile", target)
    link = CustomRule("link", target)

    mk = makefile.Makefile(
        [
            link.wrap(inputs=["a.obj", "b.obj", "c.obj"], outputs=["linked"]),
            comp.wrap(inputs=["a.code"], outputs=["a.obj"]),
            comp.wrap(inputs=["b.code"], outputs=["b.obj"]),
            comp.wrap(inputs=["gen-c.code"], outputs=["c.obj"]),
            code_gen.wrap(inputs=["c.data"], outputs=["gen-c.code"]),
        ]
    )

    assert mk.statements == [
        makefile.Statement(
            rule=comp,
            outputs=["a.obj"],
            inputs=["a.code"],
            implicit_deps=[],
        ),
        makefile.Statement(
            rule=comp,
            outputs=["b.obj"],
            inputs=["b.code"],
            implicit_deps=[],
        ),
        makefile.Statement(
            rule=code_gen,
            outputs=["gen-c.code"],
            inputs=["c.data"],
            implicit_deps=[],
        ),
        makefile.Statement(
            rule=comp,
            outputs=["c.obj"],
            inputs=["gen-c.code"],
            implicit_deps=[],
        ),
        makefile.Statement(
            rule=link,
            outputs=["linked"],
            inputs=["a.obj", "b.obj", "c.obj"],
            implicit_deps=[],
        ),
    ]

    target[:] = []
    build_result = mk.run(rt)

    assert build_result == 0
    assert target == [
        Command(
            name="compile",
            inputs=["a.code"],
            outputs=["a.obj"],
            implicit_deps=[],
        ),
        Command(
            name="compile",
            inputs=["b.code"],
            outputs=["b.obj"],
            implicit_deps=[],
        ),
        Command(
            name="code_gen",
            inputs=["c.data"],
            outputs=["gen-c.code"],
            implicit_deps=[],
        ),
        Command(
            name="compile",
            inputs=["gen-c.code"],
            outputs=["c.obj"],
            implicit_deps=[],
        ),
        Command(
            name="link",
            inputs=["a.obj", "b.obj", "c.obj"],
            outputs=["linked"],
            implicit_deps=[],
        ),
    ]

    mocker.patch(
        "os.path.getmtime",
        wraps=_mtime(
            {
                "linked": 4.0,
                "a.obj": 2.1,
                "b.obj": 2.2,
                "c.obj": 2.3,
                "gen-c.code": 1.3,
                "a.code": 1.1,
                "b.code": 1.2,
                "c.data": 5,
            }
        ),
    )

    target[:] = []
    build_result = mk.run(rt)

    assert build_result == 0
    assert target == [
        Command(
            name="code_gen",
            inputs=["c.data"],
            outputs=["gen-c.code"],
            implicit_deps=[],
        ),
        Command(
            name="compile",
            inputs=["gen-c.code"],
            outputs=["c.obj"],
            implicit_deps=[],
        ),
        Command(
            name="link",
            inputs=["a.obj", "b.obj", "c.obj"],
            outputs=["linked"],
            implicit_deps=[],
        ),
    ]


# pylint: disable-next=redefined-outer-name
def test_run_cmd(flow_cfg: env.FlowConfig, mocker):
    target: list[Output] = []

    mocker.patch.object(env.Runtime, "cmd", wraps=_log_call(target))
    rt = env.Runtime.from_flow_cfg(flow_cfg)

    mk = makefile.Makefile(
        [
            Link.statement(inputs=["a.obj", "b.obj", "c.obj"], outputs=["linked"]),
            Compile.statement(inputs=["a.code"], outputs=["a.obj"]),
            Compile.statement(inputs=["b.code"], outputs=["b.obj"]),
            Compile.statement(inputs=["gen-c.code"], outputs=["c.obj"]),
            CodeGen.statement(inputs=["c.data"], outputs=["gen-c.code"]),
            Compile.statement(inputs=["d.code"], outputs=["d.obj"]),
        ]
    )

    assert mk.statements[0].rule.run(mk.statements[0], rt) == 1

    mocker.patch(
        "os.path.getmtime",
        wraps=_mtime(
            {
                "d.obj": 2.1,
            }
        ),
    )
    target[:] = []
    build_result = mk.run(rt)

    assert build_result == 0
    assert target == [
        Exec(
            app="compile",
            args=["a.code", "-o", "a.obj"],
        ),
        Exec(
            app="compile",
            args=["b.code", "-o", "b.obj"],
        ),
        Exec(
            app="code-gen",
            args=["c.data", "-o", "gen-c.code"],
        ),
        Exec(
            app="compile",
            args=["gen-c.code", "-o", "c.obj"],
        ),
        Exec(
            app="link",
            args=["a.obj", "b.obj", "c.obj", "-o", "linked"],
        ),
    ]

    mocker.patch(
        "os.path.getmtime",
        wraps=_mtime(
            {
                "linked": 4.0,
                "a.obj": 2.1,
                "b.obj": 2.2,
                "c.obj": 2.3,
                "d.obj": 2.1,
                "gen-c.code": 1.3,
                "a.code": 1.1,
                "b.code": 1.2,
                "c.data": 5,
            }
        ),
    )

    target[:] = []
    build_result = mk.run(rt)

    assert build_result == 0
    assert target == [
        Exec(
            app="code-gen",
            args=["c.data", "-o", "gen-c.code"],
        ),
        Exec(
            app="compile",
            args=["gen-c.code", "-o", "c.obj"],
        ),
        Exec(
            app="link",
            args=["a.obj", "b.obj", "c.obj", "-o", "linked"],
        ),
    ]


# pylint: disable-next=redefined-outer-name
def test_bad_cmd(flow_cfg: env.FlowConfig, mocker):
    target: list[Output] = []

    mocker.patch.object(env.Runtime, "cmd", wraps=_bad_call(target))
    rt = env.Runtime.from_flow_cfg(flow_cfg)

    mk = makefile.Makefile(
        [
            Link.statement(inputs=["a.obj", "b.obj", "c.obj"], outputs=["linked"]),
            Compile.statement(inputs=["a.code"], outputs=["a.obj"]),
            Compile.statement(inputs=["b.code"], outputs=["b.obj"]),
            Compile.statement(inputs=["gen-c.code"], outputs=["c.obj"]),
            CodeGen.statement(inputs=["c.data"], outputs=["gen-c.code"]),
            Compile.statement(inputs=["d.code"], outputs=["d.obj"]),
        ]
    )

    mocker.patch(
        "os.path.getmtime",
        wraps=_mtime(
            {
                "linked": 4.0,
                "a.obj": 2.1,
                "b.obj": 2.2,
                "c.obj": 2.3,
                "d.obj": 2.1,
                "gen-c.code": 1.3,
                "a.code": 1.1,
                "b.code": 1.2,
                "c.data": 5,
            }
        ),
    )

    target[:] = []
    build_result = mk.run(rt)

    assert build_result == 1
    assert target == [
        Exec(
            app="code-gen",
            args=["c.data", "-o", "gen-c.code"],
        ),
    ]


# pylint: disable-next=redefined-outer-name
def test_all_fresh(flow_cfg: env.FlowConfig, mocker):
    target: list[Output] = []

    mocker.patch.object(env.Runtime, "cmd", wraps=_log_call(target))
    rt = env.Runtime.from_flow_cfg(flow_cfg)

    mk = makefile.Makefile(
        [
            Link.statement(inputs=["a.obj", "b.obj", "c.obj"], outputs=["linked"]),
            Compile.statement(inputs=["a.code"], outputs=["a.obj"]),
            Compile.statement(inputs=["b.code"], outputs=["b.obj"]),
            Compile.statement(inputs=["gen-c.code"], outputs=["c.obj"]),
            CodeGen.statement(inputs=["c.data"], outputs=["gen-c.code"]),
            Compile.statement(inputs=["d.code"], outputs=["d.obj"]),
        ]
    )

    mocker.patch(
        "os.path.getmtime",
        wraps=_mtime(
            {
                "linked": 4.0,
                "a.obj": 2.1,
                "b.obj": 2.2,
                "c.obj": 2.3,
                "d.obj": 2.1,
                "gen-c.code": 1.3,
                "a.code": 1.1,
                "b.code": 1.2,
                "c.data": 1.0,
                "d.code": 2.0,
            }
        ),
    )

    target[:] = []
    build_result = mk.run(rt)

    assert build_result == 0
    assert not target


# pylint: disable-next=redefined-outer-name
def test_dry_run(flow_cfg: env.FlowConfig, mocker):
    target: list[Output] = []

    mocker.patch.object(env.Runtime, "cmd", wraps=_log_call(target))
    rt = env.Runtime.from_flow_cfg(flow_cfg)
    link = CustomRule("link", target)

    mk = makefile.Makefile(
        [
            link.wrap(inputs=["a.obj", "b.obj", "c.obj"], outputs=["linked"]),
            Compile.statement(inputs=["a.code"], outputs=["a.obj"]),
            Compile.statement(inputs=["b.code"], outputs=["b.obj"]),
            CodeGen.statement(inputs=["c.code"], outputs=["c.obj"]),
        ]
    )

    mocker.patch(
        "os.path.getmtime",
        wraps=_mtime(
            {
                "linked": 4.0,
                "a.obj": 2.1,
                "b.obj": 2.2,
                "c.obj": 2.3,
                "a.code": 5.1,
                "b.code": 5.2,
                "c.code": 5.3,
            }
        ),
    )

    target[:] = []
    build_result = mk.run(rt)

    assert build_result == 0
    assert target == [
        Exec(app="compile", args=["a.code", "-o", "a.obj"]),
        Exec(app="compile", args=["b.code", "-o", "b.obj"]),
        Exec(app="code-gen", args=["c.code", "-o", "c.obj"]),
        Command(
            name="link",
            inputs=["a.obj", "b.obj", "c.obj"],
            outputs=["linked"],
            implicit_deps=[],
        ),
    ]

    target[:] = []
    rt.dry_run = True
    build_result = mk.run(rt)

    assert build_result == 0
    assert not target
