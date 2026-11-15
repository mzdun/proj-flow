"""Smoke tests for the ``proj-flow`` command line."""

import subprocess
import sys

from proj_flow import __version__


def run_flow(*args: str, cwd=None):
    return subprocess.run(
        [sys.executable, "-m", "proj_flow", *args],
        capture_output=True,
        text=True,
        encoding="UTF-8",
        cwd=cwd,
    )


def test_version(tmp_path):
    proc = run_flow("--version", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == f"proj-flow version {__version__}"


def test_help_lists_builtin_commands(tmp_path):
    proc = run_flow("--help", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    for command in ["init", "list", "run", "system"]:
        assert command in proc.stdout


def test_unknown_command_fails(tmp_path):
    proc = run_flow("no-such-command", cwd=tmp_path)
    assert proc.returncode != 0
