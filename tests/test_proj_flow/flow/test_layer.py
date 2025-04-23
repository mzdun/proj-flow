# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import os
from typing import cast
from unittest.mock import Mock

from proj_flow.api import ctx, env
from proj_flow.flow import layer
from proj_flow.project import interact

from ..capture import Capture
from ..mocks import FsData, fs

# from ..load_flow_cfg import flow_cfg  # noqa: F401 pylint: disable=unused-import


def _pkg(path: str):
    return os.path.join(ctx.PACKAGE_ROOT, *path.split("/"))


def _true(*_args, **_kwargs):
    return True


def setup_layer_mocks(mocker, files: FsData):
    mocker.patch("builtins.open", wraps=fs(files))
    os_makedirs = cast(Mock, mocker.patch("os.makedirs", wraps=_true))
    shutil_copymode = cast(Mock, mocker.patch("shutil.copymode", wraps=_true))
    shutil_copystat = cast(Mock, mocker.patch("shutil.copystat", wraps=_true))
    shutil_copy2 = cast(Mock, mocker.patch("shutil.copy2", wraps=_true))

    return os_makedirs, shutil_copymode, shutil_copystat, shutil_copy2


def test_gather_layers_no_flags():
    layers = layer.gather_package_layers(ctx.PACKAGE_ROOT, {})

    assert layers == [
        layer.LayerInfo(
            root=_pkg("template/layers/base"),
            files=[
                layer.FileInfo(
                    src=".clang-format",
                    dst=".clang-format",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src=".flow/config.yml",
                    dst=".flow/config.yml",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src=".flow/flow.py.mustache",
                    dst=".flow/flow.py",
                    is_mustache=True,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src=".flow/matrix.yml",
                    dst=".flow/matrix.yml",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src=".flow/official.yml",
                    dst=".flow/official.yml",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src=".gitignore",
                    dst=".gitignore",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src="README.md.mustache",
                    dst="README.md",
                    is_mustache=True,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src="flow",
                    dst="flow",
                    is_mustache=False,
                    is_executable=True,
                    when=None,
                ),
                layer.FileInfo(
                    src="flow.cmd",
                    dst="flow.cmd",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
            ],
            when=None,
        )
    ]


def test_gather_layers_full_defaults():
    rt = env.Runtime()

    context = interact.get_context(
        interact.ContextSetup(
            dest_path=None, interactive=False, simple=False, load=None
        ),
        None,
        rt,
    )
    layers = layer.gather_package_layers(ctx.PACKAGE_ROOT, context)

    assert layers == [
        layer.LayerInfo(
            root=_pkg("template/layers/github_social"),
            files=[
                layer.FileInfo(
                    src=".github/ISSUE_TEMPLATE/bug_report.md.mustache",
                    dst=".github/ISSUE_TEMPLATE/bug_report.md",
                    is_mustache=True,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src=".github/ISSUE_TEMPLATE/feature_request.md.mustache",
                    dst=".github/ISSUE_TEMPLATE/feature_request.md",
                    is_mustache=True,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src="CODE_OF_CONDUCT.md.mustache",
                    dst="CODE_OF_CONDUCT.md",
                    is_mustache=True,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src="CONTRIBUTING.md",
                    dst="CONTRIBUTING.md",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
            ],
            when="with.github.social",
        ),
        layer.LayerInfo(
            root=_pkg("template/layers/github_actions"),
            files=[
                layer.FileInfo(
                    src=".github/linters/.isort.cfg",
                    dst=".github/linters/.isort.cfg",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src=".github/linters/.mypy.ini",
                    dst=".github/linters/.mypy.ini",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src=".github/workflows/build.yml.basic",
                    dst=".github/workflows/build.yml",
                    is_mustache=False,
                    is_executable=False,
                    when="with.github.no-auto-release",
                ),
                layer.FileInfo(
                    src=".github/workflows/linter.yml",
                    dst=".github/workflows/linter.yml",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src="CPPLINT.cfg",
                    dst="CPPLINT.cfg",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
            ],
            when="with.github.actions",
        ),
        layer.LayerInfo(
            root=_pkg("template/layers/base"),
            files=[
                layer.FileInfo(
                    src=".clang-format",
                    dst=".clang-format",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src=".flow/config.yml",
                    dst=".flow/config.yml",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src=".flow/flow.py.mustache",
                    dst=".flow/flow.py",
                    is_mustache=True,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src=".flow/matrix.yml",
                    dst=".flow/matrix.yml",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src=".flow/official.yml",
                    dst=".flow/official.yml",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src=".gitignore",
                    dst=".gitignore",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src="README.md.mustache",
                    dst="README.md",
                    is_mustache=True,
                    is_executable=False,
                    when=None,
                ),
                layer.FileInfo(
                    src="flow",
                    dst="flow",
                    is_mustache=False,
                    is_executable=True,
                    when=None,
                ),
                layer.FileInfo(
                    src="flow.cmd",
                    dst="flow.cmd",
                    is_mustache=False,
                    is_executable=False,
                    when=None,
                ),
            ],
            when=None,
        ),
    ]

    names = [(layer.name, layer.pkg) for layer in layers]
    assert names == [
        ("github_social", "proj_flow"),
        ("github_actions", "proj_flow"),
        ("base", "proj_flow"),
    ]

    git_checks = list(layer.LayerInfo.get_git_checks_in(layers))
    assert git_checks == [
        layer.LayerInfo(
            root=_pkg("template/layers/base"),
            files=[
                layer.FileInfo(
                    src="flow",
                    dst="flow",
                    is_mustache=False,
                    is_executable=True,
                    when=None,
                ),
            ],
            when=None,
        ),
    ]


def test_license_none_selected(mocker):
    files: FsData = {}
    os_makedirs, shutil_copymode, shutil_copystat, shutil_copy2 = setup_layer_mocks(
        mocker, files
    )

    layer.copy_license(env.Runtime(), {})

    os_makedirs.assert_not_called()
    shutil_copymode.assert_not_called()
    shutil_copystat.assert_not_called()
    shutil_copy2.assert_not_called()


def test_license_dry_run(mocker):
    files: FsData = {}
    os_makedirs, shutil_copymode, shutil_copystat, shutil_copy2 = setup_layer_mocks(
        mocker, files
    )

    with Capture() as capture:
        layer.copy_license(
            env.Runtime(dry_run=True, silent=False, use_color=False),
            {"COPY": {"LICENSE": "Unlicense"}},
        )

    assert capture.stdout == "+ LICENSE\n"
    assert capture.stderr == ""
    os_makedirs.assert_not_called()
    shutil_copymode.assert_not_called()
    shutil_copystat.assert_not_called()
    shutil_copy2.assert_not_called()


def test_license_dry_run_colors(mocker):
    files: FsData = {}
    os_makedirs, shutil_copymode, shutil_copystat, shutil_copy2 = setup_layer_mocks(
        mocker, files
    )

    with Capture() as capture:
        layer.copy_license(
            env.Runtime(dry_run=True, silent=False, use_color=True),
            {"COPY": {"LICENSE": "Unlicense"}},
        )

    assert capture.stdout == "\x1b[2;30m+\x1b[m LICENSE\n"
    assert capture.stderr == ""
    os_makedirs.assert_not_called()
    shutil_copymode.assert_not_called()
    shutil_copystat.assert_not_called()
    shutil_copy2.assert_not_called()


def test_license_copy(mocker):
    files: FsData = {}
    files[_pkg("template/licenses/Unlicense.mustache")] = "UNLICENSE"
    os_makedirs, shutil_copymode, shutil_copystat, shutil_copy2 = setup_layer_mocks(
        mocker, files
    )

    with Capture() as capture:
        layer.copy_license(
            env.Runtime(dry_run=False, silent=True, root="/<project-dir>"),
            {"COPY": {"LICENSE": "Unlicense"}},
        )

    assert capture.stdout == ""
    assert capture.stderr == ""
    assert files["/<project-dir>/LICENSE"] == b"UNLICENSE"
    os_makedirs.assert_called_once_with("/<project-dir>", exist_ok=True)
    shutil_copymode.assert_called_once_with(
        _pkg("template/licenses/Unlicense.mustache"),
        "/<project-dir>/LICENSE",
        follow_symlinks=False,
    )
    shutil_copystat.assert_called_once_with(
        _pkg("template/licenses/Unlicense.mustache"),
        "/<project-dir>/LICENSE",
        follow_symlinks=False,
    )
    shutil_copy2.assert_not_called()


def test_copy_layer_dry_run(mocker):
    os_makedirs, shutil_copymode, shutil_copystat, shutil_copy2 = setup_layer_mocks(
        mocker, {}
    )

    test = layer.LayerInfo(
        "/code/project/src/package/template/layers/layer-name",
        files=[
            layer.FileInfo(
                src="data/file.txt",
                dst="data/file.txt",
                is_mustache=False,
                is_executable=False,
            )
        ],
    )

    with Capture() as capture:
        test.run(
            env.Runtime(
                dry_run=True, silent=False, use_color=False, root="/<project-dir>"
            ),
            {},
        )

    assert test.name == "layer-name"
    assert test.pkg == "package"
    assert capture.stdout == "[package:layer-name]\n+ data/file.txt\n\n"
    assert capture.stderr == ""
    os_makedirs.assert_not_called()
    shutil_copymode.assert_not_called()
    shutil_copystat.assert_not_called()
    shutil_copy2.assert_not_called()


def test_copy_layer_dry_run_color(mocker):
    os_makedirs, shutil_copymode, shutil_copystat, shutil_copy2 = setup_layer_mocks(
        mocker, {}
    )

    test = layer.LayerInfo(
        "/code/project/src/package/template/layers/layer-name",
        files=[
            layer.FileInfo(
                src="data/file.txt",
                dst="data/file.txt",
                is_mustache=False,
                is_executable=False,
            )
        ],
    )

    with Capture() as capture:
        test.run(
            env.Runtime(
                dry_run=True, silent=False, use_color=True, root="/<project-dir>"
            ),
            {},
        )

    assert test.name == "layer-name"
    assert test.pkg == "package"
    assert (
        capture.stdout == "\x1b[2;30m[package:layer-name]\x1b[m\n"
        "\x1b[2;30m+\x1b[m data/file.txt\n"
        "\n"
    )
    assert capture.stderr == ""
    os_makedirs.assert_not_called()
    shutil_copymode.assert_not_called()
    shutil_copystat.assert_not_called()
    shutil_copy2.assert_not_called()


def test_copy_layer(mocker):
    files: FsData = {}
    files["/code/project/src/package/template/layers/layer-name/data/file.txt"] = (
        "CONTENTS"
    )
    os_makedirs, shutil_copymode, shutil_copystat, shutil_copy2 = setup_layer_mocks(
        mocker, {}
    )

    test = layer.LayerInfo(
        "/code/project/src/package/template/layers/layer-name",
        files=[
            layer.FileInfo(
                src="data/file.txt",
                dst="data/file.txt",
                is_mustache=False,
                is_executable=False,
            )
        ],
    )

    with Capture() as capture:
        test.run(
            env.Runtime(dry_run=False, silent=True, root="/<project-dir>"),
            {},
        )

    assert capture.stdout == ""
    assert capture.stderr == ""
    assert not files.get("/<project-dir>/data/file.txt")  # open(dst) was not used
    os_makedirs.assert_called_once_with("/<project-dir>/data", exist_ok=True)
    shutil_copymode.assert_not_called()
    shutil_copystat.assert_not_called()
    shutil_copy2.assert_called_once_with(
        "/code/project/src/package/template/layers/layer-name/data/file.txt",
        "/<project-dir>/data/file.txt",
        follow_symlinks=False,
    )
