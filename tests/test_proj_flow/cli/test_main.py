# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)


import sys
from unittest.mock import Mock

from proj_flow.api import env

from ..capture import Capture
from ..mocks import fs
from . import test_argument


def _run_main():
    # pylint: disable-next=import-outside-toplevel,unused-import
    import proj_flow.__main__  # noqa: F401


def _run_main_ex():
    # pylint: disable-next=import-outside-toplevel
    from proj_flow.cli import main

    main()


def test_main(mocker):
    mocker.patch(
        "builtins.open",
        wraps=fs(
            {
                "/<project>/.flow/config.json": {
                    "entry": {"alias": ["Default", "PropA", "PropB"]}
                }
            }
        ),
    )
    mocker.patch("os.path.expanduser", wraps=lambda _: "<user-home>")
    mocker.patch("os.chdir", wraps=lambda _: ".")
    mocker.patch("os.getcwd", wraps=lambda: "/<project>")
    env.platform = "test-os"
    copy = sys.argv
    sys.argv = ["proj-flow"]
    with Capture() as capture:
        try:
            # pylint: disable-next=import-outside-toplevel,unused-import
            import proj_flow.__main__  # noqa: F401
        except SystemExit:
            pass
        finally:
            sys.argv[:] = copy

    assert capture.stdout == ""
    assert capture.stderr == test_argument.NO_CMD_ERROR


def __ctrl_c():
    raise KeyboardInterrupt()


def test_ctrl_c(mocker):
    mocker.patch("proj_flow.cli.__main", wraps=__ctrl_c)
    exception_was_sysexit: bool | None = None
    with Capture() as capture:
        copy = sys.argv
        sys.argv[:] = []
        try:
            _run_main_ex()
        except SystemExit:
            exception_was_sysexit = True
        except KeyboardInterrupt:
            exception_was_sysexit = False
        finally:
            sys.argv[:] = copy

    assert capture.stdout == ""
    assert capture.stderr == ""
    assert isinstance(exception_was_sysexit, bool)
    assert exception_was_sysexit


def test_dash_see(mocker):
    chdir: Mock = mocker.patch("os.chdir", wraps=lambda s: 0)
    copy = [*sys.argv]
    with Capture() as capture:
        sys.argv[:] = ["proj-flow", "-C", "dirname", "bootstrap"]
        try:
            _run_main_ex()
        except SystemExit:
            pass
        finally:
            sys.argv[:] = copy

    chdir.assert_called_once_with("dirname")
    assert capture.stdout == ""
    assert capture.stderr == ""
