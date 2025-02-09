# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.dependency** verifies availabilty of Step's external tools.
"""

import re
import sys
from dataclasses import dataclass
from enum import Enum
from importlib.metadata import version as package_version
from typing import Callable, List, Set, Tuple, cast

from proj_flow.base import cmd

VER_REGEX = re.compile(r"((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*))")
Version = Tuple[int, int, int]


class DepKind(Enum):
    APP = "app"
    PYTHON_PKG = "python_pkg"


def _ver(ver: str) -> Version:
    chunks = [int(v.strip()) for v in ver.split(".")]
    while len(chunks) < 3:
        chunks.append(0)
    return cast(Tuple[int, int, int], (*chunks[:3],))


@dataclass
class Comp:
    op: str
    check: Callable[[Version, Version], bool]


def _compatible(app: Version, exp: Version):
    return app[0] == exp[0] and app[1] >= exp[1]


_comparisons: List[Comp] = [
    Comp("==", lambda app, exp: app == exp),
    Comp(">=", lambda app, exp: app >= exp),
    Comp("<=", lambda app, exp: app <= exp),
    Comp("~=", _compatible),
    Comp("!=", lambda app, exp: app != exp),
    Comp("<", lambda app, exp: app < exp),
    Comp(">", lambda app, exp: app > exp),
]


@dataclass
class Dependency:
    name: str
    version_expression: str
    kind: DepKind = DepKind.APP

    def __lt__(self, rhs: "Dependency"):
        if self.kind != rhs.kind:
            return self.kind.value < rhs.kind.value
        if self.name != rhs.name:
            return self.name < rhs.name
        return self.version_expression < rhs.version_expression

    def __eq__(self, rhs: "Dependency"):
        return (
            self.kind == rhs.kind
            and self.name == rhs.name
            and self.version_expression == rhs.version_expression
        )

    def match_version(self, version: str):
        for expression in (expr.strip() for expr in self.version_expression.split(",")):
            if not self._match_version(version, expression):
                return f"{self.name}: version `{version}` does not match `{expression}`"
        return None

    def _match_version(self, version: str, expression: str):
        if expression == "":
            return True
        app = _ver(version)
        for comp in _comparisons:
            if not expression.startswith(comp.op):
                continue
            return comp.check(app, _ver(expression[len(comp.op) :].lstrip()))

        return False  # there is some other permutation of "=><!~"


def gather(steps: list):
    deps: Set[str] = set()
    for step in steps:
        deps.update(step.platform_dependencies())

    result: List[Dependency] = []
    for dep in deps:
        split = re.split(r"([=><!~])", dep, 1)
        app = split.pop(0).strip()
        version = "".join(split).strip()

        kind = DepKind.APP
        app_keys = app.split()
        if len(app_keys) > 2 and app_keys[0] == "python" and app_keys[1] == "-m":
            app = " ".join(app_keys[2:])
            kind = DepKind.PYTHON_PKG

        result.append(Dependency(app, version, kind))

    return result


def verify(deps: List[Dependency]):
    uniq: List[Dependency] = []
    errors: Set[str] = set()
    for dep in sorted(deps):
        if len(uniq) == 0 or uniq[-1] != dep:
            uniq.append(dep)

    for pkg in (dep for dep in uniq if dep.kind == DepKind.PYTHON_PKG):
        try:
            version = package_version(pkg.name)
        except Exception as ex:
            errors.add(f"{pkg.name}: Python package is missing: {ex}")
            continue
        msg = pkg.match_version(version)
        if msg is not None:
            errors.add(msg)

    for app in (dep for dep in uniq if dep.kind == DepKind.APP):
        if not cmd.is_tool(app.name):
            errors.add(f"{app.name}: tool is missing")
            continue
        proc = cmd.run(app.name, "--version", capture_output=True)
        if not proc:
            version = None
        elif proc.returncode:
            if proc.stderr:
                print(proc.stderr.rstrip(), file=sys.stderr)
            version = None
        else:
            m = VER_REGEX.search(proc.stdout)
            version = m.group(0) if m is not None else None

        if version is None and app.version_expression != "":
            errors.add(
                f"{app.name}: could not read version for `{app.version_expression}`"
            )
            continue
        msg = version and app.match_version(version)
        if msg is not None:
            errors.add(msg)

    return list(sorted(errors))
