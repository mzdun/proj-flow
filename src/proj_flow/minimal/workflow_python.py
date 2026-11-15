# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.minimal.workflow_python** checks, if the GitHub workflows of
the project set up a Python version, which *Project Flow* can run on. Used by
``./flow bootstrap``.
"""

import re
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Iterator, List, Optional, cast

import yaml

from proj_flow.api import env
from proj_flow.dependency import Dependency, DepKind

#: Runs of *Project Flow* recognized in the ``run`` scripts of the steps.
RUN_PATTERNS = [
    re.compile(r"\bpython[\d.]*\s+-m\s+proj_flow\b"),
    re.compile(r"(?<![\w./-])proj-flow(?![\w-])"),
    re.compile(r"(?<![\w])\.flow/flow\.py\b"),
    re.compile(r"(?<![\w./])\./flow(?![\w./-])"),
]

#: Actions installing *Project Flow* with the Python they set up.
BOOTSTRAP_ACTIONS = ["proj-flow-actions/bootstrap", "proj-flow/actions/bootstrap"]

#: Actions setting up Python, taking ``python-version`` input.
PYTHON_ACTIONS = ["actions/setup-python", *BOOTSTRAP_ACTIONS]

# "3.12", "3.12.4", "pypy3.10", "3.13-dev"; anything else (ranges, "3.x",
# expressions) cannot be checked reliably
_EXACT_VERSION = re.compile(r"^(?:pypy)?(\d+\.\d+)(?:\.\d+)?(?:-dev)?$")


@dataclass
class PythonSetup:
    """
    Python version set up by a step of a job, which also runs *Project Flow*.
    """

    #: Path of the workflow file.
    workflow: Path
    #: Name of the job.
    job: str
    #: Name of the step setting up the Python.
    step: str
    #: Version, as written in the workflow or in the version file.
    version: str


def required_python() -> Optional[str]:
    """
    Find the Python versions *Project Flow* supports, from the
    ``Requires-Python`` of the installed package.

    :returns: version requirement, e.g. ``>=3.12``, or ``None``, if the
        package is not installed or does not name one
    """
    try:
        return metadata.metadata("proj-flow").get("Requires-Python") or None
    except metadata.PackageNotFoundError:
        return None


_LOWER_BOUND = re.compile(r"(?:>=|~=|==)\s*(\d+\.\d+)")


def workflow_python_version() -> str:
    """
    Pick the Python version for the workflows of a new project: the lowest
    version allowed by :func:`required_python`, e.g. ``3.12`` for
    ``>=3.12``. If there is no such bound, the version running *Project
    Flow* is used.

    :returns: ``major.minor`` version, e.g. ``3.12``
    """
    required = required_python()
    if required:
        match = _LOWER_BOUND.search(required)
        if match:
            return match.group(1)
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _uses(step: dict, actions: List[str]) -> bool:
    uses = step.get("uses")
    if not isinstance(uses, str):
        return False
    action = uses.split("@", 1)[0]
    return any(action == name or action.endswith(f"/{name}") for name in actions)


def _runs_proj_flow(step: dict) -> bool:
    if _uses(step, BOOTSTRAP_ACTIONS):
        return True
    script = step.get("run")
    if not isinstance(script, str):
        return False
    return any(pattern.search(script) for pattern in RUN_PATTERNS)


def _versions_of(step: dict, root: Path) -> List[str]:
    inputs = cast(dict, step.get("with") or {})
    version = inputs.get("python-version")
    if version is not None:
        # a list of versions is one version per line
        return [line.strip() for line in str(version).splitlines() if line.strip()]

    version_file = inputs.get("python-version-file") or ".python-version"
    if "${{" in str(version_file):
        return []
    try:
        lines = (root / str(version_file)).read_text(encoding="UTF-8").splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def _step_name(step: dict) -> str:
    return str(step.get("name") or step.get("uses") or step.get("run", "")[:40])


def python_setups(root: Path) -> Iterator[PythonSetup]:
    """
    Find the Python versions set up in the jobs of the GitHub workflows,
    which also run *Project Flow*, either through
    ``proj-flow-actions/bootstrap``, or by calling ``proj-flow``,
    ``python -m proj_flow``, ``.flow/flow.py`` or ``./flow``. Versions are
    taken from ``python-version`` of ``actions/setup-python`` and
    ``proj-flow-actions/bootstrap`` steps, from their ``python-version-file``,
    or from ``.python-version``, if neither is given.

    :param root: root directory of the project
    :returns: the Python setups, one for each version
    """
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return

    for path in sorted(workflows.iterdir()):
        if path.suffix not in (".yml", ".yaml"):
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="UTF-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue

        jobs = data.get("jobs")
        if not isinstance(jobs, dict):
            continue

        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            steps = [step for step in job.get("steps") or [] if isinstance(step, dict)]
            if not any(_runs_proj_flow(step) for step in steps):
                continue

            job_name = str(job.get("name") or job_id)
            for step in steps:
                if not _uses(step, PYTHON_ACTIONS):
                    continue
                for version in _versions_of(step, root):
                    yield PythonSetup(path, job_name, _step_name(step), version)


def incompatible_setups(root: Path, required: str) -> List[PythonSetup]:
    """
    Find the Python setups from :func:`python_setups`, whose version does
    not meet the requirement. Versions, which cannot be checked reliably,
    such as ranges, ``3.x`` or ``${{ ... }}`` expressions, are skipped.

    :param root: root directory of the project
    :param required: version requirement, e.g. ``>=3.12``
    :returns: the setups with incompatible versions
    """
    python = Dependency("python", required, DepKind.APP)
    result: List[PythonSetup] = []
    for setup in python_setups(root):
        match = _EXACT_VERSION.match(setup.version)
        if not match:
            continue
        if python.match_version(match.group(1)) is not None:
            result.append(setup)
    return result


def warn_about_workflows(rt: env.Runtime):
    """
    Print a warning for each GitHub workflow job, which runs *Project Flow*
    on a Python version it does not support. Nothing is printed, if the
    supported versions are not known, and the check never fails the command.

    :param rt: runtime of current call
    """
    required = required_python()
    if not required:
        if rt.verbose:
            rt.message("bootstrap: supported Python versions are unknown")
        return

    try:
        setups = incompatible_setups(rt.root, required)
    except Exception as ex:  # the check is advisory only
        if rt.verbose:
            rt.message(f"bootstrap: cannot check the workflows: {ex}")
        return

    for setup in setups:
        try:
            workflow = setup.workflow.relative_to(rt.root).as_posix()
        except ValueError:
            workflow = setup.workflow.as_posix()
        message = (
            f"-- {workflow}: job `{setup.job}`, step `{setup.step}` sets up "
            f"Python {setup.version}, but proj-flow requires Python {required}"
        )
        if rt.use_color:
            message = f"\033[1;33m{message}\033[m"
        print(message, file=sys.stderr)
