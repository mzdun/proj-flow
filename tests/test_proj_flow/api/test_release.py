# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import argparse
import os
import re
from typing import Optional

import pytest

from proj_flow.api import env, release

from ..load_flow_cfg import load_flow_cfg
from ..mocks import OS_PATH_ISFILE, FsData, fs, wrap_fs


@pytest.fixture
def flow_cfg(mocker):
    return load_flow_cfg(mocker, user_cfg=None, proj_cfg=None)


def _args(**kwargs):
    return argparse.Namespace(**kwargs)


class ProjectSuite(release.ProjectSuite):
    def get_project(self, rt: env.Runtime) -> Optional[release.Project]:
        path = self.get_version_file_path(rt)
        if not path:
            return None

        return self.get_project_impl(path)

    def get_project_impl(self, path: str) -> Optional[release.Project]:
        with open(path, encoding="UTF-8") as inf:
            lines = inf.readlines()

        project_name: str | None = None
        project_version: release.Arg | None = None
        offset = 0

        for line in lines:
            this_line = len(line)
            offset += this_line

            chunk = line.split("#", 1)[0].strip().split(":", 1)
            if len(chunk) < 2:
                continue

            if line.startswith("PROJECT: "):
                project_name = line[len("PROJECT: ") :].strip()
                if project_version:
                    break
                continue

            if not line.startswith("VERSION: "):
                continue

            prefix = len("VERSION: ")
            value = line[prefix:]
            prefix += len(value)
            value = value.lstrip()
            prefix -= len(value)
            project_version = release.Arg(value.rstrip(), offset - this_line + prefix)
            if project_name:
                break

        if not project_name or not project_version:
            return None

        version = project_version.value
        core = re.split(r"([0-9]+\.[0-9]+\.[0-9]+)", version, maxsplit=1)[1]
        stability = version[len(core) :]
        core_arg = release.Arg(core, project_version.offset)
        stability_arg = release.Arg(stability, project_version.offset + len(core))
        return release.Project(
            project_name,
            release.Version(core_arg, stability_arg),
        )

    def get_version_file_path(self, rt: env.Runtime) -> Optional[str]:
        return os.path.join(rt.root, "<project.file>")


class ProjectSuite2(ProjectSuite):
    def get_project(self, rt: env.Runtime) -> Optional[release.Project]:
        path = super().get_version_file_path(rt)
        if not path:
            return None

        return self.get_project_impl(path)

    def get_version_file_path(self, _rt: env.Runtime) -> Optional[str]:
        return None


class ProjectSuite3(ProjectSuite):
    def get_version_file_path(self, _rt: env.Runtime) -> Optional[str]:
        return None


# pylint: disable-next=redefined-outer-name
def test_project(flow_cfg: env.FlowConfig, mocker):
    rt = env.Runtime.from_flow_cfg(flow_cfg)
    files: FsData = {
        "/<project-root>/<project.file>": ""
        "PROJECT: magic-tool\n"
        "VERSION: 1.2.3\n"
        "AFTER: value\n"
    }
    wrap_fs({"<project-root>": {"<project.file>": True}}, mocker, OS_PATH_ISFILE)
    mocker.patch("builtins.open", wraps=fs(files))

    suite = ProjectSuite()
    project = suite.get_project(rt)

    assert project
    assert project.package_root == "magic-tool"
    assert str(project.version) == "1.2.3"
    assert project.archive_name == "magic-tool-1.2.3"
    assert project.tag_name == "v1.2.3"
    assert project.package_prefix == "magic-tool-1.2.3-"
    assert project.package_suffix == ""

    suite.set_version(rt, "2.0.0-rc.3")
    project = suite.get_project(rt)
    assert project
    assert project.tag_name == "v2.0.0-rc.3"

    suite.set_version(rt, "2.0.1")
    project = suite.get_project(rt)
    assert project
    assert project.tag_name == "v2.0.1"

    suite2 = ProjectSuite2()
    suite2.set_version(rt, "0.1.0")
    project = suite2.get_project(rt)
    assert project
    assert project.tag_name != "v0.1.0"

    release.project_suites.container = []
    release.project_suites.add(ProjectSuite)

    project = release.get_project(rt)
    assert project
    assert project.package_root == "magic-tool"
    assert str(project.version) == "2.0.1"
    assert project.archive_name == "magic-tool-2.0.1"
    assert project.tag_name == "v2.0.1"
    assert project.package_prefix == "magic-tool-2.0.1-"
    assert project.package_suffix == ""

    release.project_suites.container = []
    release.project_suites.add(ProjectSuite3)

    exception_risen = False
    try:
        project = release.get_project(rt)
    except SystemExit:
        exception_risen = True

    assert exception_risen
