# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from proj_flow.base import cmd


def test_is_tool(mocker):
    mocker.patch(
        "shutil.which",
        wraps=lambda tool: f"/path/{tool}" if not tool.startswith("not-") else None,
    )
    assert cmd.is_tool("a-tool")
    assert not cmd.is_tool("not-a-tool")


def test_run(mocker):
    mocker.patch(
        "shutil.which",
        wraps=lambda tool: f"/path/{tool}" if not tool.startswith("not-") else None,
    )
    run = mocker.patch("subprocess.run", wraps=lambda *arg, **kwargs: arg)

    assert cmd.run("a-tool", "arg1", "arg2") is not None
    assert cmd.run("not-a-tool", "arg1", "arg2") is None
    run.assert_called_once_with(
        ["/path/a-tool", "arg1", "arg2"],
        encoding="UTF-8",
        check=False,
        capture_output=False,
    )


def test_cd(mocker):
    getcwd = mocker.patch("os.getcwd", wraps=lambda: "old-path")
    chdir = mocker.patch("os.chdir")

    with cmd.cd("new-path"):
        getcwd.assert_called_once()
        chdir.assert_called_with("new-path")
    chdir.assert_called_with("old-path")
