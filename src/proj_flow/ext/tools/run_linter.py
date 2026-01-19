# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import shlex
import subprocess
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, cast

import requests_cache
from yaml import load, safe_load

from proj_flow.api.arg import Argument, command
from proj_flow.api.env import Runtime

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

IMAGE = "github/super-linter"
PREFIX = f"{IMAGE}/"


@dataclass
class Image:
    repo: str
    name: str
    version: str

    @property
    def full_name(self):
        return f"{self.repo}/{self.name}"

    @property
    def label(self):
        return f"{self.repo}/{self.name}:{self.version}"

    def super_linter_args(self, env: dict[str, str], log_level: str):
        _env = env.copy()
        _env["RUN_LOCAL"] = "true"
        _env["LOG_LEVEL"] = log_level
        _env["USE_FIND_ALGORITHM"] = "true"
        _env["VALIDATE_ALL_CODEBASE"] = "true"

        args = [
            arg
            for pair in (["-e", f"{key}={_env[key]}"] for key in _env)
            for arg in pair
        ]
        return [
            "docker",
            "run",
            "--rm",
            *args,
            "-v" f"{Path().absolute().as_posix()}:/tmp/lint",
            self.label,
        ]


@dataclass
class Step:
    name: str
    image: Image
    env: dict[str, str]


@dataclass
class Job:
    name: str
    steps: list[Step]


@command("tools", "run-linter")
def run_linter(
    log_level: Annotated[
        str,
        Argument(
            help="Select one of log levels (defaults to INFO)",
            choices=["ERROR", "WARN", "NOTICE", "INFO", "DEBUG"],
            default="INFO",
            opt=True,
        ),
    ],
    rt: Runtime,
):
    """Run dockerized super-linter with all the settings from local GitHub workflows"""

    WORKFLOWS = Path(".github/workflows")
    if not WORKFLOWS.is_dir():
        if not rt.silent:
            print("This project has no GitHub workflows")
            return 0

    db_path = Path("build")
    db_path.mkdir(parents=True, exist_ok=True)
    db_path = db_path / "cache_db"

    session = requests_cache.CachedSession(db_path)
    JOBS: list[Job] = []
    for root, dirs, files in WORKFLOWS.walk():
        for filename in files:
            path = root / filename
            if path.suffix not in [".yml", ".yaml"]:
                continue

            with path.open(encoding="UTF-8") as f:
                data = load(f, Loader=Loader)
                try:
                    yml_name = cast(str, data["name"])
                except KeyError:
                    yml_name = path.stem
                JOBS.extend(_get_linter_actions(data, yml_name, session, rt.verbose))

    for job in JOBS:
        job_name, steps = job.name, job.steps
        print(f"job:  \033[1;49;95m{job_name}\033[m")
        for step in steps:
            print(
                f"step: \033[1;49;96m{step.name}\033[m \033[2;49;32m({step.image.full_name}:\033[0;49;32m{step.image.version}\033[2;49;32m)\033[m"
            )
            args = step.image.super_linter_args(step.env, log_level=log_level)
            print("\033[0;49;30m{}\033[m".format(shlex.join(args)))
            subprocess.run(args, shell=False)
            print()


def _download_docker_image_id(
    action: str,
    version: str | None,
    session: requests_cache.CachedSession,
    verbose: bool,
):
    if action != IMAGE and not action.startswith(PREFIX):
        return None

    repo = "https://raw.githubusercontent.com/github/super-linter"
    refs = f"refs/tags/{version}" if version else "refs/heads/main"
    filename = "action.yml"
    if action.startswith(PREFIX):
        filename = f"{action[len(PREFIX):]}/{filename}"

    url = f"{repo}/{refs}/{filename}"
    if verbose:
        print("-- run-linter: Downloading", url)
    response = session.get(url)
    response.raise_for_status()
    data = cast(dict[str, dict[str, str]], safe_load(response.text))
    runs = data.get("runs", {})
    if runs.get("using") != "docker":
        return None

    image = runs.get("image")
    if not image:
        return None

    url = urllib.parse.urlparse(image)
    name, version = url.path[1:].split(":", 1)
    return Image(url.netloc, name, version)


def _get_linter_action(
    step: dict, session: requests_cache.CachedSession, verbose: bool
):
    try:
        id_parts = cast(str, step["uses"]).split("@", 1)
    except KeyError:
        return

    action = id_parts[0]
    action_version = id_parts[1] if len(id_parts) > 1 else None
    image = _download_docker_image_id(action, action_version, session, verbose)
    if not image:
        return

    try:
        name = cast(str, step["name"])
    except KeyError:
        name = cast(str, step["uses"])

    if verbose:
        print(f'-- run-linter: Found {image.label} used by "{name}"')

    try:
        env = cast(dict[str, Any], step["env"])
    except KeyError:
        env = {}

    _env: dict[str, str] = {}
    for key in env:
        value = env[key]
        if isinstance(value, bool):
            _env[key] = "true" if value else "false"
            continue
        if isinstance(value, str) and "${{" in value:
            continue
        _env[key] = value

    return Step(name=name, image=image, env=_env)


def _get_linter_actions(
    data: dict, yml_name: str, session: requests_cache.CachedSession, verbose: bool
):
    result: list[Job] = []
    for job_id, job in cast(dict[str, dict], data["jobs"]).items():
        steps: list[Step] = []
        for step_def in cast(list[dict], job["steps"]):
            step = _get_linter_action(step_def, session, verbose)
            if step is None:
                continue
            steps.append(step)

        if not steps:
            continue

        try:
            name = cast(str, job["name"])
        except KeyError:
            name = job_id

        if name != yml_name:
            name = f"{yml_name} » {name}"

        result.append(Job(name=name, steps=steps))

    return result
