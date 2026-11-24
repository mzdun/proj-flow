"""Tests for the docker command line built in ``proj_flow.ext.tools.run_linter``."""

from proj_flow.ext.tools import run_linter

IMAGE = run_linter.Image("ghcr.io", "super-linter/super-linter", "slim-v8.5.0")


def _docker_env(args: list[str]):
    env: dict[str, str] = {}
    for flag, value in zip(args, args[1:]):
        if flag == "-e":
            key, val = value.split("=", 1)
            env[key] = val
    return env


def test_github_only_settings_are_dropped():
    step_env = {
        "DEFAULT_BRANCH": "main",
        "ENABLE_GITHUB_ACTIONS_STEP_SUMMARY": "true",
        "ENABLE_GITHUB_PULL_REQUEST_SUMMARY_COMMENT": "true",
        "GITHUB_DOMAIN": "github.example.com",
        "MULTI_STATUS": "true",
        "VALIDATE_CPP": "true",
        "VALIDATE_ALL_CODEBASE": "false",
    }

    env = _docker_env(IMAGE.super_linter_args(step_env, log_level="ERROR"))

    assert env == {
        "VALIDATE_CPP": "true",
        "VALIDATE_ALL_CODEBASE": "true",
        "RUN_LOCAL": "true",
        "LOG_LEVEL": "ERROR",
        "USE_FIND_ALGORITHM": "true",
        "MULTI_STATUS": "false",
    }
    assert "DEFAULT_BRANCH" in step_env


def test_command_runs_the_image():
    args = IMAGE.super_linter_args({}, log_level="INFO")

    assert args[:3] == ["docker", "run", "--rm"]
    assert args[-1] == "ghcr.io/super-linter/super-linter:slim-v8.5.0"
    assert args[-2].endswith(":/tmp/lint")
