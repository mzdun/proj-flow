# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from prompt_toolkit.document import Document
from prompt_toolkit.validation import ValidationError, Validator

from proj_flow import __version__
from proj_flow.api import env
from proj_flow.flow import steps
from proj_flow.project import api, interact

from ..load_flow_cfg import CONFIG, MATRIX, flow_cfg, load_flow_cfg
from ..mocks import FsData, fs
from . import project_fubar

DUMMY = [project_fubar, flow_cfg]


def _faux_prompt(
    message: str | list[tuple[str, str]], validator: None | Validator = None, **_kwargs
):
    if isinstance(message, list):
        message = "".join(msg for _, msg in message)

    if validator:
        try:
            validator.validate(Document())
            assert True
        except ValidationError:
            assert False

    if message.endswith(" [yes / no]: "):
        return "no"
    return ""


def test_interact_defaults_overriden(mocker):
    mocker.patch("os.chdir", wraps=lambda _: ".")
    mocker.patch("os.getcwd", wraps=lambda: "/<project>")
    env.platform = "test-os"
    flow_cfg = load_flow_cfg(  # pylint: disable=redefined-outer-name
        mocker,
        user_cfg={
            "defaults": {
                "PROJECT.EMAIL": "johnny.appleseed@example.com",
                "COPY.HOLDER": "Johnny Appleseed",
            }
        },
        proj_cfg=CONFIG,
        matrix=MATRIX,
    )
    steps.clean_aliases(flow_cfg)

    try:
        fubar = api.get_project_type("foo-bar")
        assert fubar
    except api.ProjectNotFound:
        assert False

    rt = env.Runtime.from_flow_cfg(flow_cfg)

    setup = interact.ContextSetup(
        dest_path="here/we/go", interactive=False, simple=True, load=None
    )
    context = fubar.get_context(setup, rt)

    assert context == {
        "PROJECT": {
            "NAME": "go",
            "DESCRIPTION": "",
            "EMAIL": "johnny.appleseed@example.com",
        },
        "COPY": {"YEAR": 2025, "HOLDER": "Johnny Appleseed", "LICENSE": "MIT"},
        "SRCDIR": "src",
        "fubar": {"key": "", "switch": False},
        "FAULTY": {"KEY": "not-a-dict", "VALUE": "", "EMPTY": ""},
        "SWITCH": {"OFF": False},
        "with": {"github": {"actions": True, "auto-release": False, "social": True}},
    }

    setup.simple = False
    context = fubar.get_context(setup, rt)

    assert context == {
        "PROJECT": {
            "NAME": "go",
            "DESCRIPTION": "",
            "EMAIL": "johnny.appleseed@example.com",
        },
        "COPY": {"YEAR": 2025, "HOLDER": "Johnny Appleseed", "LICENSE": "MIT"},
        "SRCDIR": "src",
        "__flow_version__": __version__,
        "fubar": {"key": "", "switch": False},
        "FAULTY": {"KEY": "not-a-dict", "VALUE": "", "EMPTY": ""},
        "SWITCH": {"OFF": False},
        "with": {
            "github": {
                "actions": True,
                "auto-release": False,
                "no-auto-release": True,
                "social": True,
            }
        },
        "${": "${",
    }


# pylint: disable-next=redefined-outer-name
def test_interact_defaults(mocker, flow_cfg: env.FlowConfig):  # noqa: F811
    files: FsData = {
        "override.yml": {
            "PROJECT.EMAIL": "johnny.appleseed@example.com",
            "COPY.HOLDER": "Johnny Appleseed",
        }
    }
    mocker.patch("builtins.open", wraps=fs(files))

    try:
        fubar = api.get_project_type("foo-bar")
        assert fubar
    except api.ProjectNotFound:
        assert False

    rt = env.Runtime.from_flow_cfg(flow_cfg)

    setup = interact.ContextSetup(
        dest_path="here/we/go", interactive=False, simple=True, load="override.yml"
    )
    context = fubar.get_context(setup, rt)

    assert context == {
        "PROJECT": {
            "NAME": "go",
            "DESCRIPTION": "",
            "EMAIL": "johnny.appleseed@example.com",
        },
        "COPY": {"YEAR": 2025, "HOLDER": "Johnny Appleseed", "LICENSE": "MIT"},
        "SRCDIR": "src",
        "fubar": {"key": "", "switch": False},
        "FAULTY": {"KEY": "not-a-dict", "VALUE": "", "EMPTY": ""},
        "SWITCH": {"OFF": False},
        "with": {"github": {"actions": True, "auto-release": False, "social": True}},
    }

    setup.simple = False
    context = fubar.get_context(setup, rt)

    assert context == {
        "PROJECT": {
            "NAME": "go",
            "DESCRIPTION": "",
            "EMAIL": "johnny.appleseed@example.com",
        },
        "COPY": {"YEAR": 2025, "HOLDER": "Johnny Appleseed", "LICENSE": "MIT"},
        "SRCDIR": "src",
        "__flow_version__": __version__,
        "fubar": {"key": "", "switch": False},
        "FAULTY": {"KEY": "not-a-dict", "VALUE": "", "EMPTY": ""},
        "SWITCH": {"OFF": False},
        "with": {
            "github": {
                "actions": True,
                "auto-release": False,
                "no-auto-release": True,
                "social": True,
            }
        },
        "${": "${",
    }


# pylint: disable-next=redefined-outer-name
def test_interact_prompt(mocker, flow_cfg: env.FlowConfig):  # noqa: F811
    files: FsData = {
        "override.yml": {
            "PROJECT.EMAIL": "johnny.appleseed@example.com",
            "COPY.HOLDER": "Johnny Appleseed",
            "COPY.LICENSE": "Zlib",
        }
    }
    mocker.patch("builtins.open", wraps=fs(files))
    mocker.patch("proj_flow.project.interact.tk_prompt", wraps=_faux_prompt)

    rt = env.Runtime.from_flow_cfg(flow_cfg)
    setup = interact.ContextSetup(
        dest_path="here/we/go", interactive=True, simple=False, load="override.yml"
    )
    context = interact.get_context(setup, None, rt)

    assert context == {
        "PROJECT": {
            "NAME": "go",
            "DESCRIPTION": "",
            "EMAIL": "johnny.appleseed@example.com",
        },
        "COPY": {"YEAR": 2025, "HOLDER": "Johnny Appleseed", "LICENSE": "Zlib"},
        "SRCDIR": "src",
        "FAULTY": {"KEY": "not-a-dict", "VALUE": "", "EMPTY": ""},
        "SWITCH": {"OFF": False},
        "with": {
            "github": {
                "actions": False,
                "auto-release": False,
                "social": False,
                "no-auto-release": True,
            }
        },
        "__flow_version__": "0.16.0",
        "${": "${",
    }
