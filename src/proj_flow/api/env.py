# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.api.env** provides interaction with project environment:

- :class:`FlowConfig` loads the project config in ``.flow/config.yml``.
- :class:`Runtime` provides means to run tools and print messages, while
  respecting ``--dry-run``, ``--silent`` and ``--verbose``.
- :class:`Config` represents single run configuration.
"""

import argparse
import importlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union, cast

from proj_flow.api import ctx
from proj_flow.base import plugins, uname
from proj_flow.base.cmake_presets import get_binary_dirs

platform = uname.uname()[0]


_flow_config_default_compiler: Optional[Dict[str, str]] = None


class CMakeBinaryDirsCache:
    """
    Build directories of the presets in ``CMakePresets.json`` of current
    directory, read on first use.
    """

    _dirs: dict[str, Path] | None = None
    _loaded: bool = False

    @property
    def dirs(self):
        """
        Build directories, keyed by preset name, or ``None``, if there are no
        presets.
        """
        if not self._loaded:
            self._loaded = True
            self._dirs = get_binary_dirs()

        return self._dirs

    def binary_dir(self, key: str):
        """
        Build directory of a preset.

        :param key: name of the preset
        :returns: the directory, or ``None``, if the preset is unknown
        """
        return (self.dirs or {}).get(key)


#: Shared cache of CMake build directories, used by :attr:`Config.build_dir`.
CMAKE_BINARY_DIRS = CMakeBinaryDirsCache()


def default_compiler():
    """
    Name of the compiler to use on current platform: the ``DEV_CXX``
    environment variable, or the ``compiler.os-default`` entry of the project
    config. Prints a warning and returns ``"?"``, if neither is available.

    :returns: compiler name, e.g. ``gcc``
    """
    try:
        return os.environ["DEV_CXX"]
    except KeyError:
        pass

    flow_config_default_compiler = _flow_config_default_compiler or {}

    try:
        return flow_config_default_compiler[platform]
    except KeyError:
        print(
            f"-- KeyError: {platform} in {flow_config_default_compiler}",
            file=sys.stderr,
        )
        return "?"
    except TypeError:
        print(f"-- TypeError: internal: flow config not ready yet", file=sys.stderr)
        return "?"


class Printer:
    """
    Prints command lines to stderr, masking secrets and, optionally,
    coloring the arguments.
    """

    @staticmethod
    def hide(arg: str, secrets: List[str]):
        """
        Mask the secrets in an argument with question marks.

        :param arg: argument to mask
        :param secrets: values to mask
        :returns: the masked argument
        """
        for secret in secrets:
            arg = arg.replace(secret, "?" * max(15, len(secret)))
        return arg

    @staticmethod
    def print_arg(arg: str, secrets: List[str], raw: bool):
        """
        Format one argument for a colored command line: options are dimmed,
        quoted arguments are blue.

        :param arg: argument to format
        :param secrets: values to mask
        :param raw: print the argument as is, without shell quoting
        :returns: the formatted argument
        """
        color = ""
        arg = Printer.hide(arg, secrets)
        if arg[:1] == "-":
            color = "\033[2;37m"
        if not raw:
            arg = shlex.join([arg])
        if color == "" and arg[:1] in ["'", '"']:
            color = "\033[2;34m"
        if color == "":
            return arg
        return f"{color}{arg}\033[m"

    @staticmethod
    def print_cmd(*args: str, use_color: bool = True, secrets: List[str], raw: bool):
        """
        Print a command line to stderr.

        :param args: program and its arguments
        :param use_color: color the program and the arguments
        :param secrets: values to mask
        :param raw: print the arguments as they are, without shell quoting
        """
        cmd = args[0] if raw else shlex.join([args[0]])
        if not use_color:
            if raw:
                print(
                    cmd,
                    *(Printer.hide(arg, secrets) for arg in args[1:]),
                    file=sys.stderr,
                )
            else:
                print(
                    cmd,
                    shlex.join(Printer.hide(arg, secrets) for arg in args[1:]),
                    file=sys.stderr,
                )
            return

        printed = " ".join([Printer.print_arg(arg, secrets, raw) for arg in args[1:]])
        print(f"\033[33m{cmd}\033[m {printed}", file=sys.stderr)


@dataclass
class RunAlias:
    """
    Command running a fixed list of steps, declared in the ``entry`` section
    of the project config.
    """

    #: Name of the command, e.g. ``build``.
    name: str

    #: Help of the command.
    doc: str

    #: Names of the steps to run.
    steps: List[str]

    @staticmethod
    def from_json(name: str, alias: Union[dict, list]):
        """
        Read an alias from the project config.

        :param name: name of the command
        :param alias: list of step names, or an object with ``steps`` and,
            optionally, ``doc``
        :returns: the alias; its help defaults to
            ``Shortcut for "run -s <steps>"``
        """
        if isinstance(alias, dict):
            doc: str = alias.get("doc", "")
            steps: List[str] = alias.get("steps", [])
        else:
            doc = ""
            steps = alias
        if not doc:
            doc = f'Shortcut for "run -s {",".join(steps)}"'

        return RunAlias(name, doc, steps)


def _merge_dicts(dst: dict, src: dict):
    for key in src:
        if key not in dst:
            dst[key] = src[key]
            continue

        src_val = src[key]
        dst_val = dst[key]

        if isinstance(src_val, dict):
            if isinstance(dst_val, dict):
                _merge_dicts(dst_val, src_val)
                continue

        dst[key] = src_val


def _flatten_dict(dst: ctx.SettingsType, defaults: Dict[str, Any], prefix=""):
    for key, val in defaults.items():
        this_key = f"{prefix}{key}"

        if isinstance(val, dict):
            _flatten_dict(dst, val, f"{this_key}.")
            continue

        if val is None:
            dst[this_key] = ""
            continue

        if isinstance(val, bool):
            dst[this_key] = val
            continue

        dst[this_key] = str(val)


def _merge(cfg: dict, defaults: ctx.SettingsType, path: Path):
    config = plugins.load_data(path)
    if not isinstance(config, dict):
        return

    stored_defaults = config.get("defaults", {})
    try:
        del config["defaults"]
    except KeyError:
        pass

    _merge_dicts(cfg, config)

    if isinstance(stored_defaults, dict):
        _flatten_dict(defaults, stored_defaults)


def load_extensions(extensions: List[str]):
    """
    Import extension modules, so they can register their commands, steps and
    plugins. Errors are printed and do not stop the other extensions from
    loading.

    :param extensions: names of the modules to import
    """
    for extension in extensions:
        try:
            importlib.import_module(extension)
        except ImportError as ex:
            print(
                f"-- error: loading module `{extension}` resulted in import error: {ex}",
                file=sys.stderr,
            )
        except BaseException as ex:
            te = traceback.TracebackException(
                type(ex), ex, ex.__traceback__, limit=None, compact=True
            )

            print(
                f"-- error: there was an error while loading module `{extension}`: {ex}\n\nTraceback (most recent call last):",
                file=sys.stderr,
            )
            print("".join(te.stack.format()))


class FlowConfig:
    """
    Project configuration, merged from the user config in
    ``~/.config/proj-flow.*`` and the project config in ``.flow/config.*``.
    Loading the configuration also loads the extensions it lists.

    :param cfg: configuration to copy; when given, ``root`` is ignored and
        nothing is loaded
    :param root: root directory of the project
    """

    _cfg: dict
    steps: list = []
    aliases: List[RunAlias] = []
    root: Path

    def __init__(self, cfg: Optional["FlowConfig"] = None, root: Path = Path()):
        if cfg is not None:
            self._cfg = cfg._cfg
            self.steps = cfg.steps
            self.aliases = cfg.aliases
            self.root = cfg.root
        else:
            self.root = root.absolute()
            defaults: ctx.SettingsType = {}
            dest: dict = {}

            _merge(
                dest,
                defaults,
                Path("~").expanduser() / ".config" / "proj-flow.json",
            )
            _merge(dest, defaults, self.root / ".flow" / "config.json")

            self._cfg = dest
            self._cfg["defaults"] = defaults

            self._propagate_compilers()
            self._load_extensions()

    def _propagate_compilers(self):
        global _flow_config_default_compiler
        _flow_config_default_compiler = self.compiler_os_default

    def _load_extensions(self):
        extensions = cast(List[str], self._cfg.get("extensions", []))
        extensions.insert(0, "proj_flow.minimal")

        local_extensions = (self.root / ".flow" / "extensions").resolve()
        if local_extensions.is_dir():
            sys.path.insert(0, local_extensions.as_posix())

        load_extensions(extensions)

    @property
    def items(self):
        """
        Whole merged configuration, for reading sections owned by extensions.
        """
        return self._cfg

    @property
    def entry(self) -> Dict[str, dict]:
        """
        The ``entry`` section: run aliases, each one a list of step names or
        an object with ``steps`` and ``doc``.
        """
        return self._cfg.get("entry", {})

    @property
    def compiler(self) -> Dict[str, dict]:
        """The ``compiler`` section."""
        return self._cfg.get("compiler", {})

    @property
    def compiler_names(self) -> Dict[str, List[str]]:
        """
        The ``compiler.names`` section: compiler executables for each
        compiler name, e.g. ``gcc: [gcc, g++]``.
        """
        return self.compiler.get("names", {})

    @property
    def compiler_os_default(self) -> Dict[str, str]:
        """
        The ``compiler.os-default`` section: default compiler name for each
        platform, e.g. ``ubuntu: gcc``.
        """
        return self.compiler.get("os-default", {})

    @property
    def lts_list(self) -> Dict[str, List[str]]:
        """
        The ``lts`` section: supported system versions for each platform.
        ``lts.ubuntu`` is deprecated, Ubuntu versions are calculated from
        current date.
        """
        return self._cfg.get("lts", {})

    @property
    def postproc(self) -> dict:
        """
        The ``postproc`` section, adjusting the run configurations after the
        matrix is built.
        """
        return self._cfg.get("postproc", {})

    @property
    def postproc_exclude(self) -> List[dict]:
        """
        The ``postproc.exclude`` section: configurations matching any of these
        partial configurations are removed.
        """
        return self.postproc.get("exclude", [])

    @property
    def postproc_include(self) -> List[dict]:
        """
        The ``postproc.include`` section: configurations matching any of
        these partial configurations get the values they are missing.
        """
        return self.postproc.get("include", [])

    @property
    def shortcuts(self) -> Dict[str, dict]:
        """
        The ``shortcuts`` section: named sets of ``-D`` values, available as
        ``--<name>`` switches, e.g. ``dbg: {build_type: Debug}``.
        """
        return self._cfg.get("shortcuts", {})

    @property
    def default_branch(self) -> str:
        """Branch, from which releases are made; ``main``, unless configured otherwise."""
        return cast(str, self._cfg.get("default-branch", "main")) or "main"


def _mkdir(dirname: str):
    os.makedirs(dirname, exist_ok=True)


def _ls(dirname: str, shallow=True):
    result = []
    for root, dirnames, filenames in os.walk(dirname):
        if shallow:
            dirnames[:] = []

        result.extend(
            os.path.relpath(os.path.join(root, filename), start=dirname)
            for filename in filenames
        )
    return result


def _cp(src: str, dst: str) -> int:
    try:
        dst = os.path.abspath(dst)
        if os.path.isdir(src):
            _mkdir(dst)
            shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)
        else:
            if not os.path.isdir(dst):
                _mkdir(os.path.dirname(dst))
            shutil.copy(src, dst, follow_symlinks=False)
        return 0
    except FileNotFoundError as err:
        print(err, file=sys.stderr)
        return 1


class Msg(Enum):
    """Message level for Runtime.message"""

    DEBUG = 0
    """Print only, when verbose is set"""

    STATUS = 2
    """Print when silent if not set"""

    ALWAYS = 3
    """Print always"""


MSG_GUARD: Dict[Msg, Callable[["Runtime"], bool]] = {
    Msg.DEBUG: lambda rt: rt.verbose,
    Msg.STATUS: lambda rt: not rt.silent,
    Msg.ALWAYS: lambda rt: True,
}


class Runtime(FlowConfig):
    """
    Project configuration, together with the state of current run: the
    ``--dry-run``, ``--silent``, ``--verbose`` and ``--official`` switches,
    coloring and the platform.

    :param argsOrRuntime: parsed command line to read the switches from, or
        another runtime to copy them from
    :param cfg: project configuration
    """

    dry_run: bool
    silent: bool
    verbose: bool
    official: bool
    no_coverage: bool
    use_color: bool
    only_host: bool
    platform: str
    secrets: List[str] = []

    def __init__(
        self, argsOrRuntime: Union[argparse.Namespace, "Runtime"], cfg: FlowConfig
    ):
        super().__init__(cfg=cfg)

        if isinstance(argsOrRuntime, argparse.Namespace):
            args = argsOrRuntime
            self.dry_run = getattr(args, "dry_run", False)
            self.silent = getattr(args, "silent", False)
            self.verbose = getattr(args, "verbose", False)
            self.official = getattr(args, "official", False)
            self.use_color = True
            self.no_coverage = False
            self.platform = platform

            if "NO_COVERAGE" in os.environ:
                self.no_coverage = True

            if "RELEASE" in os.environ and "GITHUB_ACTIONS" in os.environ:
                self.official = not not json.loads(os.environ["RELEASE"])

            self.only_host = not (self.dry_run or self.official)
        else:
            rt = argsOrRuntime
            self.dry_run = rt.dry_run
            self.silent = rt.silent
            self.verbose = rt.verbose
            self.official = rt.official
            self.no_coverage = rt.no_coverage
            self.use_color = rt.use_color
            self.only_host = rt.only_host
            self.platform = rt.platform
            self.secrets = [*rt.secrets]

    def message(self, *args: str, level=Msg.DEBUG, **kwargs):
        """
        Print a ``--``-prefixed message to stderr, if the level allows it.

        :param args: values to print, as with :py:func:`print`
        :param level: importance of the message; by default, printed only
            with ``--verbose``
        :param kwargs: other arguments of :py:func:`print`
        """
        if not MSG_GUARD[level](self):
            return

        print("--", *args, **kwargs, file=sys.stderr)

    def fatal(self, *args: str, **kwargs):
        """
        Print an error to stderr and exit with code 1.

        :param args: values to print, as with :py:func:`print`
        :param kwargs: other arguments of :py:func:`print`
        """
        print("-- FATAL:", *args, **kwargs, file=sys.stderr)
        sys.exit(1)

    def print(self, *args: str, raw=False):
        """
        Print a command line to stderr, unless ``--silent``, masking the
        :attr:`secrets`.

        :param args: program and its arguments
        :param raw: print the arguments as they are, without shell quoting
        """
        if not self.silent:
            Printer.print_cmd(
                *args, use_color=self.use_color, secrets=self.secrets, raw=raw
            )

    def cmd(self, *args: str) -> int:
        """
        Print and run a command, which changes something. With ``--dry-run``,
        the command is only printed. A failing command exits the program.

        :param args: program and its arguments
        :returns: ``0``
        """
        self.print(*args)
        if self.dry_run:
            return 0

        result = subprocess.run(args)
        if result.returncode != 0:
            print(
                f"proj-flow: error: {args[0]} ended in failure, exiting",
                file=sys.stderr,
            )
            raise SystemExit(1)
        return 0

    def capture(self, *args: str, silent=False):
        """
        Run a command and capture its output. The command runs even with
        ``--dry-run``, so use it only for commands, which change nothing.

        :param args: program and its arguments
        :param silent: do not print the command
        :returns: the finished process, with text ``stdout`` and ``stderr``
        """
        if not silent:
            self.print(*args)
        return subprocess.run(args, shell=False, encoding="UTF-8", capture_output=True)

    def mkdirs(self, dirname: str) -> int:
        """
        Create a directory with its parents, unless ``--dry-run``.

        :param dirname: directory to create
        :returns: ``0``
        """
        self.print("mkdir", "-p", dirname)

        if self.dry_run:
            return 0

        os.makedirs(dirname, exist_ok=True)
        return 0

    def cp(self, src: str, dst: str, regex: Optional[str] = None):
        """
        Copy a file or a directory, unless ``--dry-run``.

        :param src: file or directory to copy
        :param dst: destination path
        :param regex: copy only the files directly in ``src``, whose names
            match this expression
        :returns: ``0`` on success, ``1``, if a file was missing
        """
        args = ["cp"]
        if os.path.isdir(src):
            args.append("-r")
        self.print(*args, src, dst)

        if self.dry_run:
            return 0

        if regex is None:
            return _cp(src, dst)

        files = _ls(src)
        files = (name for name in files if re.match(regex, name))
        for name in files:
            result = _cp(os.path.join(src, name), os.path.join(dst, name))
            if result:
                return result
        return 0


@dataclass
class Config:
    """
    Single run configuration, one entry of the matrix from ``.flow``, as
    filtered by ``-D`` switches.
    """

    #: Values of the configuration, e.g. ``os``, ``build_type`` or
    #: ``compiler``.
    items: dict

    #: Keys of the matrix.
    keys: List[str]

    def get_path(self, key: str, val: Any = None):
        """
        Read a nested value.

        :param key: dotted path to the value, e.g. ``coverage`` for
            a top-level matrix value
        :param val: value to return, if the path is missing
        :returns: the value, or ``val``
        """
        path = key.split(".")
        ctx = self.items
        for step in path:
            if not isinstance(ctx, dict):
                return val
            child = ctx.get(step)
            if child is None:
                return val
            ctx = child
        return cast(Any, ctx)

    @property
    def os(self) -> str:
        """Operating system of the configuration, e.g. ``ubuntu``."""
        return self.items.get("os", "")

    @property
    def compiler(self) -> List[str]:
        """Compiler executables, e.g. ``["gcc", "g++"]``."""
        return self.items.get("compiler", [])

    @property
    def build_type(self) -> str:
        """Build type, e.g. ``Debug`` or ``Release``."""
        return self.items.get("build_type", "")

    @property
    def build_name(self) -> str:
        """Human-readable name of the configuration, shown during the run."""
        return self.items.get("build_name", "")

    @property
    def build_dir(self) -> Path:
        """
        Build directory: the one of the CMake preset named
        ``<preset>-<build_generator>``, if there is one, otherwise
        ``build/<preset>``.
        """
        cmake_binary_dir = CMAKE_BINARY_DIRS.binary_dir(
            f"{self.preset}-{self.build_generator}"
        )
        if cmake_binary_dir:
            return cmake_binary_dir
        return Path("build") / self.preset

    @property
    def preset(self) -> str:
        """Name of the CMake preset."""
        return self.items.get("preset", "")

    @property
    def build_generator(self) -> str:
        """Name of the build generator, part of the CMake preset name."""
        return self.items.get("build_generator", "")
