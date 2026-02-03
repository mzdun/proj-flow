# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import concurrent.futures
import os
import shutil
import subprocess
import sys
import tempfile
from os import PathLike
from pathlib import Path
from typing import Annotated, Any, Generator, cast

from proj_flow.api import arg, env, release
from proj_flow.base.cmake_presets import Presets
from proj_flow.ext.test_runner.driver.commands import HANDLERS
from proj_flow.ext.test_runner.driver.test import Env, Test
from proj_flow.ext.test_runner.driver.testbed import Counters, task

RUN_LINEAR = os.environ.get("RUN_LINEAR", 0) != 0


@arg.command("tools", "test-runner")
def test_runner(
    preset_name: Annotated[
        str,
        arg.Argument(
            help="Set name of CMake build preset",
            meta="CONFIG",
            names=["--preset"],
        ),
    ],
    tests: Annotated[
        str,
        arg.Argument(
            help="Point to directory with the JSON test cases; test cases are enumerated recursively",
            meta="DIR",
        ),
    ],
    version: Annotated[
        str | None,
        arg.Argument(
            help="Select version to patch output with; defaults to automatic detection",
            meta="SEMVER",
            opt=True,
        ),
    ],
    run: Annotated[
        list[str],
        arg.Argument(
            help="Filter the tests to run",
            meta="ID",
            action="extend",
            opt=True,
            nargs="*",
            default=[],
        ),
    ],
    nullify: Annotated[
        bool,
        arg.FlagArgument(
            help='Set the "expected" field of the test cases to null',
        ),
    ],
    rt: env.Runtime,
) -> int:
    """Run specified test steps"""

    if os.name == "nt":
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore

    if not version:
        proj = release.get_project(rt)
        version = str(proj.version)

    presets = Presets().visit_file(Path("CMakePresets.json")) or {}
    preset = presets.get(preset_name)

    if preset is None:
        print(f"error: preset `{preset_name}` not found", file=sys.stderr)
        return 1

    binary_dir = preset.expand()
    build_type = preset.build_type

    if not binary_dir:
        print(
            f"error: preset `{preset_name}` has no binaryDir attached to it",
            file=sys.stderr,
        )
        return 1

    if not build_type:
        print(
            f"error: preset `{preset_name}` has no CMAKE_BUILD_TYPE attached to it",
            file=sys.stderr,
        )
        return 1

    config = cast(dict, rt._cfg.get("test-runner", {}))
    target = cast(str | None, config.get("target"))

    if not isinstance(target, str):
        print(
            "error: cannot find test target; "
            "please add name of the executable as `target' property of "
            "`test-runner' config in flow's configuration file",
            file=sys.stderr,
        )
        return 1

    ext = ".exe" if sys.platform == "win32" else ""
    target_path = Path(binary_dir) / "bin" / (target + ext)
    if not target_path.is_file():
        print(
            f"error: cannot find {target + ext} in {target_path.parent.as_posix()}",
            file=sys.stderr,
        )
        return 1

    install_components = cast(list[str], config.get("install", []))
    patches = cast(dict[str, str], config.get("patches"))
    env_prefix = cast(str | None, config.get("report_env"))

    testsuite_config = cast(dict, config.get("testsuite", {}))
    test_root = cast(str | None, testsuite_config.get("root"))
    test_root_path = Path(test_root).resolve() if test_root else None
    if not test_root_path:
        print(
            "error: cannot find test root directory; "
            "please add name of the directory as `root' property of "
            "`test-runner/testsuite' config in flow's configuration file",
            file=sys.stderr,
        )
        return 1

    test_data_dir = cast(str | None, testsuite_config.get("data"))
    data_dir = (
        (test_root_path / test_data_dir).resolve()
        if isinstance(test_data_dir, str)
        else None
    )

    test_default_set = cast(str | None, testsuite_config.get("default-set"))
    if isinstance(test_default_set, str):
        if (
            not (test_root_path / tests).is_dir()
            and (test_root_path / test_default_set / tests).is_dir()
        ):
            tests = f"{test_default_set}/{tests}"

    test_set_dir = test_root_path / tests

    test_files = _enum_tests(test_set_dir, data_dir)
    tests_to_run = [int(x) for s in (run or []) for x in s.split(",")]
    if not tests_to_run:
        tests_to_run = list(range(1, len(test_files) + 1))

    independent_tests, linear_tests = _load_tests(test_files, tests_to_run)

    if nullify:
        for sequence in (independent_tests, linear_tests):
            for test in sequence:
                test[0].nullify(lang=None)
        return 0

    if not independent_tests and not linear_tests:
        print("No tests to run.", file=sys.stderr)
        return 0

    env = _make_env(
        target_path,
        data_dir or Path(binary_dir),
        version,
        len(independent_tests) + len(linear_tests),
        patches,
        env_prefix,
    )

    print("target: ", env.target, env.version)
    if env.data_dir_alt is None:
        print("data:   ", env.data_dir)
    else:
        print("data:   ", env.data_dir, env.data_dir_alt)
    print("tests:  ", tests)
    if env.tempdir_alt is None:
        print("$TEMP:  ", env.tempdir)
    else:
        print("$TEMP:  ", env.tempdir, env.tempdir_alt)

    os.makedirs(env.tempdir, exist_ok=True)

    install_dir = Path("build").resolve() / ".test-runner"
    if not _install(
        install_dir,
        binary_dir,
        build_type,
        install_components,
        env,
    ):
        return 1

    return _run_and_report_tests(
        independent_tests=independent_tests,
        linear_tests=linear_tests,
        install_dir=install_dir,
        env=env,
    )


def _run_and_report_tests(
    independent_tests: list[tuple[Test, int]],
    linear_tests: list[tuple[Test, int]],
    install_dir: Path,
    env: Env,
):
    RUN_LINEAR = os.environ.get("RUN_LINEAR", 0) != 0
    if RUN_LINEAR:
        linear_tests[0:0] = independent_tests
        independent_tests = []

    counters = Counters()

    if independent_tests:
        try:
            thread_count = int(os.environ.get("POOL_SIZE", "not-a-number"))
        except (ValueError, TypeError):
            thread_count = max(1, (os.cpu_count() or 0)) * 2
        print("threads:", thread_count)

        _report_tests(counters, _run_async_tests(independent_tests, env, thread_count))

    _report_tests(counters, _run_sync_tests(linear_tests, env))

    shutil.rmtree(install_dir, ignore_errors=True)
    shutil.rmtree("build/.testing", ignore_errors=True)

    if not counters.summary(len(independent_tests) + len(linear_tests)):
        return 1

    return 0


def _run_async_tests(tests: list[tuple[Test, int]], env: Env, thread_count: int):
    with concurrent.futures.ThreadPoolExecutor(thread_count) as executor:
        futures: list[concurrent.futures.Future[tuple[int, str, str | None, str]]] = []
        for test, counter in tests:
            futures.append(executor.submit(task, env, test, counter))

        for future in concurrent.futures.as_completed(futures):
            yield future.result()


def _run_sync_tests(tests: list[tuple[Test, int]], env: Env):
    for test, counter in tests:
        yield task(env, test, counter)


def _report_tests(
    counters: Counters,
    results: Generator[tuple[int, str, str | None, str], Any, None],
):
    for outcome, test_id, message, tempdir in results:
        counters.report(outcome, test_id, message)
        shutil.rmtree(tempdir, ignore_errors=True)


def _enum_tests(test_root: Path, data_dir: Path | None):
    test_files: list[Path] = []
    for root, _, files in test_root.walk():
        for filename in files:
            if not Path(filename).suffix in [".json", ".yaml", ".yml"]:
                continue
            test_path = root / filename
            if data_dir and test_path.is_relative_to(data_dir):
                continue
            test_files.append(test_path)

    return test_files


def _load_tests(testsuite: list[Path], run: list[int]):
    counter: int = 0
    independent_tests: list[tuple[Test, int]] = []
    linear_tests: list[tuple[Test, int]] = []

    for filename in sorted(testsuite):
        counter += 1
        if counter not in run:
            continue

        try:
            test = Test.load(filename, counter)
            if not test.ok:
                continue
        except Exception:
            print(">>>>>>", filename.as_posix(), file=sys.stderr)
            raise

        if test.linear:
            linear_tests.append((test, counter))
        else:
            independent_tests.append((test, counter))

    return independent_tests, linear_tests


def _cmake_executable(binary_dir: str | PathLike[str]):
    cache = Path(binary_dir) / "CMakeCache.txt"
    if not cache.is_file():
        return "cmake"

    with cache.open(encoding="UTF-8") as cache_file:
        for line in cache_file:
            line = line.strip()
            if not line.startswith("CMAKE_COMMAND:INTERNAL="):
                continue
            return line.split("=", 1)[1]

    return "cmake"


def _run_with(test: Test, *args: str):
    cwd = None if test.linear else test.cwd
    subprocess.run(args, shell=False, cwd=cwd)


def _target(target: str):
    def impl(test: Test, aditional: list[str]):
        _run_with(test, target, *aditional)

    return impl


def _make_env(
    target: Path,
    data_dir: Path,
    version: str,
    counter_total: int,
    patches: dict[str, str],
    env_prefix: str | None,
):
    target_name = target.stem if os.name == "nt" else target.name
    tempdir = (Path(tempfile.gettempdir()) / "test-runner").resolve()
    tempdir_alt = None
    data_dir_alt = None

    if os.sep != "/":
        tempdir_alt = str(tempdir)
        data_dir_alt = str(data_dir)

    length = counter_total
    digits = 1
    while length > 9:
        digits += 1
        length = length // 10

    return Env(
        target=str(target),
        target_name=target_name,
        build_dir=str(target.parent.parent),
        data_dir=data_dir.as_posix(),
        inst_dir=str(data_dir.parent / "copy" / "bin"),
        tempdir=tempdir.as_posix(),
        version=version,
        counter_digits=digits,
        counter_total=counter_total,
        handlers=HANDLERS,
        data_dir_alt=data_dir_alt,
        tempdir_alt=tempdir_alt,
        builtin_patches=patches,
        reportable_env_prefix=env_prefix,
    )


def _install(
    dst: str | PathLike[str],
    binary_dir: str | PathLike[str],
    build_type: str,
    components: list[str],
    env: Env,
):
    dst = Path(dst)
    shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True, exist_ok=True)

    args = [
        _cmake_executable(binary_dir),
        "--install",
        str(binary_dir),
        "--config",
        build_type,
        "--prefix",
        str(dst),
    ]

    if not components:
        proc = subprocess.run(args, capture_output=True)
        return proc.returncode == 0

    args.append("--component")
    args.append("")

    for component in components:
        args[-1] = component
        proc = subprocess.run(args, capture_output=True)
        if proc.returncode != 0:
            return False

    env.target = str(dst / "bin" / os.path.basename(env.target))
    target_name = os.path.split(env.target)[1]
    if os.name == "nt":
        target_name = os.path.splitext(target_name)[0]
    env.handlers[target_name] = (0, _target(env.target))

    return True
