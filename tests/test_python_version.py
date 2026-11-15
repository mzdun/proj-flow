"""Tests for reading Python project versions in ``proj_flow.ext.python.version``."""

import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from proj_flow.ext.python.version import ProjectSuite


def _runtime(root: Path):
    # ProjectSuite only needs the project root from the runtime
    return SimpleNamespace(root=root)


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="UTF-8")


HATCH_DYNAMIC = """
    [project]
    name = "my-package"
    dynamic = ["version"]

    [tool.hatch.version]
    path = "src/my_package/__init__.py"

    [tool.hatch.build.targets.wheel]
    packages = ["src/my_package"]
"""


@pytest.mark.parametrize(
    "line, core, stability",
    [
        ('__version__ = "1.2.3"', "1.2.3", ""),
        ("__version__ = 'v0.36.0'", "0.36.0", ""),
        ('VERSION = "2.0.0-rc.1"', "2.0.0", "-rc.1"),
    ],
)
def test_dynamic_version(tmp_path, line, core, stability):
    _write(tmp_path / "pyproject.toml", HATCH_DYNAMIC)
    _write(tmp_path / "src/my_package/__init__.py", f'"""doc"""\n\n{line}\n')

    project = ProjectSuite().get_project(_runtime(tmp_path))

    assert project is not None
    assert project.package_root == "my_package"
    assert project.version.core.value == core
    assert project.version.stability.value == stability
    assert project.tag_name == f"v{core}{stability}"
    assert project.archive_name == f"my_package-{core}{stability}"

    # offsets point at the version inside the file
    text = (tmp_path / "src/my_package/__init__.py").read_text(encoding="UTF-8")
    offset = project.version.core.offset
    assert text[offset : offset + len(core)] == core


def test_custom_pattern(tmp_path):
    _write(
        tmp_path / "pyproject.toml",
        """
        [project]
        name = "pkg"
        dynamic = ["version"]

        [tool.hatch.version]
        path = "version.txt"
        pattern = "release: (?P<version>.+)"
        """,
    )
    _write(tmp_path / "version.txt", "release: 3.4.5\n")

    project = ProjectSuite().get_project(_runtime(tmp_path))

    assert project is not None
    assert project.package_root == "pkg"
    assert str(project.version) == "3.4.5"


def test_missing_version_file(tmp_path):
    _write(tmp_path / "pyproject.toml", HATCH_DYNAMIC)
    assert ProjectSuite().get_project(_runtime(tmp_path)) is None


def test_no_pyproject(tmp_path):
    suite = ProjectSuite()
    assert suite.get_project(_runtime(tmp_path)) is None
    assert suite.get_version_file_path(_runtime(tmp_path)) is None


def test_static_version_points_to_pyproject(tmp_path):
    _write(
        tmp_path / "pyproject.toml",
        """
        [project]
        name = "static"
        version = "1.0.0"
        """,
    )
    assert ProjectSuite().get_version_file_path(_runtime(tmp_path)) == "pyproject.toml"


def test_this_repository():
    root = Path(__file__).resolve().parent.parent
    project = ProjectSuite().get_project(_runtime(root))

    from proj_flow import __version__

    assert project is not None
    assert project.package_root == "proj_flow"
    assert str(project.version) == __version__
