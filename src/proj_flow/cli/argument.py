# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.cli.argument** provides command-line builders and runners,
supporting the functions decorated with :func:`@arg.command()
<proj_flow.api.arg.command>`.
"""

import argparse
import shutil
import sys
import textwrap
import typing
from dataclasses import dataclass, field

from proj_flow import __version__
from proj_flow.api import arg, completers, env, step
from proj_flow.base import inspect as _inspect
from proj_flow.base import registry
from proj_flow.flow import configs


class Completer(typing.Protocol):
    """
    Shell completion function attached to an argparse action, as expected by
    ``argcomplete``.
    """

    def __call__(self, **kwarg) -> typing.Any: ...


class Action(typing.Protocol):
    """
    Argparse action with a shell completer attached.
    """

    #: Completion function for the values of the action.
    completer: Completer


class Subparsers(typing.Protocol):
    """
    Result of :meth:`Parser.add_command_subparsers`: argparse subparsers
    creating :class:`Parser` instances, which know their parent parser.
    """

    #: Parser owning these subparsers.
    parent: "Parser"

    def add_parser(*args, **kwargs) -> "Parser":
        """
        Create the parser of one command.

        :param args: arguments passed to the argparse ``add_parser``
        :param kwargs: keyword arguments passed to the argparse ``add_parser``
        :returns: the parser of the command
        """
        ...


class Parser(argparse.ArgumentParser):
    """
    Argument parser of *Project Flow*, which also finds and runs the selected
    command or alias.

    :param kwargs: arguments passed to :class:`argparse.ArgumentParser`
    """

    flow: env.FlowConfig
    menu: typing.List["Command"]
    shortcuts: typing.Dict[str, typing.List[str]]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def add_command_subparsers(self, **kwargs) -> Subparsers:
        """
        Add the subparsers for the commands, typed so they create
        :class:`Parser` instances and can point back to their parent.

        :param kwargs: arguments passed to
            :meth:`argparse.ArgumentParser.add_subparsers`
        """
        return typing.cast(Subparsers, self.add_subparsers(**kwargs))

    def find_and_run_command(self, args: argparse.Namespace):
        """
        Run the command selected on the command line. An alias from the
        ``entry`` section of the flow config runs the ``run`` command with
        the steps of the alias. With ``--verbose``, all the registered commands,
        steps and plugins are listed first. If no known command is selected,
        exit with the list of known commands and aliases.

        :param args: parsed command line
        :returns: exit code of the command
        """
        commands = {entry.name for entry in self.menu}
        aliases = self.flow.aliases

        rt = env.Runtime(args, self.flow)

        if rt.verbose:
            verbose_info(self.menu)
            step.verbose_info()
            registry.verbose_info()

        if args.command in commands:
            command = _first(lambda command: command.name == args.command, self.menu)
            if command:
                return command.run(args, rt)
        elif args.command in {alias.name for alias in aliases}:
            command = _first(lambda command: command.name == "run", self.menu)
            alias = _first(lambda alias: alias.name == args.command, aliases)
            if command and alias:
                args.cli_steps.append(",".join(alias.steps))
                return command.run(args, rt)

        lines = ["the command arguments are required; known commands:", ""]
        for command in self.menu:
            lines.append(f"  - {command.name}: {command.doc}")
        for alias in aliases:
            lines.append(f"  - {alias.name}: {alias.doc}")

        self.error("\n".join(lines))


def build_argparser(flow_cfg: env.FlowConfig):
    """
    Build the parser for the whole command line: the global options, all the
    commands registered with :func:`@arg.command() <proj_flow.api.arg.command>`
    and the ``run`` aliases from the flow config.

    :param flow_cfg: configuration of current project
    :returns: the parser
    """
    parser = Parser(
        prog="proj-flow",
        description="C++ project maintenance, automated",
        add_help=False,
    )
    parser.add_argument(
        "-h", "--help", action="help", help="Show this help message and exit"
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        default=argparse.SUPPRESS,
        version=f"%(prog)s version {__version__}",
        help="Show proj-flow's version and exit",
    )
    parser.add_argument(
        "-C",
        metavar="dir",
        nargs="?",
        help="Run as if proj-flow was started in <dir> instead of the current "
        "working directory. This directory must exist.",
    ).completer = completers.cd_completer  # type: ignore

    menu = _build_menu(arg.get_commands(), None)
    _argparse_visit_all(parser, flow_cfg, menu.children)
    return parser


def expand_shortcuts(parser: Parser, args: argparse.Namespace):
    """
    Replace a shortcut flag from the ``shortcuts`` section of the flow config,
    e.g. ``--both``, with its ``-D`` values. Only the first shortcut set on
    the command line is used.

    :param parser: parser knowing the shortcuts
    :param args: parsed command line; its ``configs`` list is extended
    """
    args_kwargs = dict(args._get_kwargs())
    shortcuts: typing.Dict[str, typing.List[str]] = parser.shortcuts
    for key in shortcuts:
        try:
            if not args_kwargs[key]:
                continue
            typing.cast(typing.List[str], args.configs).extend(shortcuts[key])
            break
        except KeyError:
            continue


@dataclass
class AdditionalArgument:
    """
    Parameter of a command function, which is not a command-line argument,
    but an object created for the call, such as
    :class:`Runtime <proj_flow.api.env.Runtime>` or :class:`Command`.
    """

    #: Name of the function parameter.
    name: str
    #: Type of the parameter; any type other than ``Runtime`` and ``Command``
    #: is called with the runtime and the parsed command line.
    ctor: callable  # type: ignore

    def create(self, rt: env.Runtime, args: argparse.Namespace, menu: "Command"):
        """
        Create the value passed to the command function.

        :param rt: runtime of current call
        :param args: parsed command line
        :param menu: command being called
        :returns: depending on the ``ctor``, current runtime, current command
            or a new ``ctor(rt, args)`` object
        """
        if self.ctor == env.Runtime:
            return rt
        if self.ctor == Command:
            return menu
        return self.ctor(rt, args)


@dataclass
class AnnotatedArgument:
    """
    Parameter of a command function annotated with
    :class:`arg.Argument <proj_flow.api.arg.Argument>`, i.e. a command-line
    argument.
    """

    #: Name of the function parameter.
    name: str
    #: Description of the command-line argument.
    argument: arg.Argument

    @property
    def group(self):
        """Mutually exclusive group of the argument, if any."""
        return self.argument.group

    def argparse_visit(self, parser: argparse._ActionsContainer):
        """
        Add the argument to the parser.

        :param parser: parser or argument group to add to
        """
        return self.argument.visit(parser, self.name)


AnyArgument = typing.Union[AdditionalArgument, AnnotatedArgument]


@dataclass
class Command:
    """
    Node of the command tree built from the functions decorated with
    :func:`@arg.command() <proj_flow.api.arg.command>`.
    """

    #: Name of this level of the command, e.g. ``matrix`` in ``github matrix``.
    name: str
    #: Help of the command, the docstring of the function.
    doc: str
    #: The decorated function.
    entry: callable  # type: ignore
    #: Command-line arguments of the function.
    annotated: typing.List[AnnotatedArgument]
    #: Other parameters of the function.
    additional: typing.List[AdditionalArgument]
    #: Parent command, ``None`` for top-level commands.
    parent: typing.Optional["Command"]
    #: Subcommands.
    children: typing.List["Command"] = field(default_factory=list)

    def argparse_visit(
        self,
        subparsers: Subparsers,
        alias: typing.Optional[str] = None,
        doc: typing.Optional[str] = None,
        level=0,
    ):
        """
        Add the parser of this command, with its arguments and subcommands.

        :param subparsers: subparsers of the parent command
        :param alias: name to register the command under, defaults to
            :attr:`name`
        :param doc: help to use, defaults to :attr:`doc`
        :param level: depth of the command; subcommands are stored in
            ``command_<level>`` of the parsed command line
        """
        if not doc:
            doc = self.doc
        if not alias:
            alias = self.name

        parser = subparsers.add_parser(
            alias, help=doc.split("\n\n")[0], description=doc, add_help=False
        )

        parent = subparsers.parent
        parser.flow = parent.flow
        parser.shortcuts = parent.shortcuts

        assert parent.flow is not None
        assert parent.shortcuts is not None

        _argparse_runtime_visit(parser)

        has_config = False
        for additional in self.additional:
            if additional.ctor == configs.Configs:
                has_config = True
                break

        if has_config:
            _argparse_config_visit(parser)

        groups: typing.Set[int] = set()
        for arg_index in range(len(self.annotated)):
            annotated = self.annotated[arg_index]
            group = annotated.group
            if group is not None:
                if id(group) in groups:
                    continue
                groups.add(id(group))
                group_container = group.visit(parser)
                for sub_index in range(arg_index, len(self.annotated)):
                    sub = self.annotated[sub_index]
                    if sub.group is group:
                        sub.argparse_visit(group_container)
                continue
            annotated.argparse_visit(parser)

        if len(self.children):
            subparsers = parser.add_command_subparsers(
                dest=f"command_{level}",
                metavar="command",
                help="Known command name, see below",
            )
            subparsers.parent = parser

            for entry in self.children:
                entry.argparse_visit(subparsers, level=level + 1)

    def run(self, args: argparse.Namespace, rt: env.Runtime, level=0):
        """
        Call the selected subcommand, or the function of this command. A
        command grouping other commands, whose function has an empty body,
        reports the missing subcommand instead.

        :param args: parsed command line
        :param rt: runtime of current call
        :param level: depth of the command
        :returns: exit code; ``0``, if the function returned ``None``
        """
        if level == 0 and rt.only_host:
            rt.only_host = self.name == "run"

        subcommand_name = None

        if len(self.children):
            subcommand_attribute = f"command_{level}"
            if hasattr(args, subcommand_attribute):
                subcommand_name = getattr(args, subcommand_attribute)

        if subcommand_name is not None:
            subcommand = _first(
                lambda command: command.name == subcommand_name, self.children
            )
            if not subcommand:
                rt.fatal(f"cannot find {subcommand_name}")

            return subcommand.run(args, rt, level=level + 1)

        if len(self.children) and _inspect.has_empty_body(self.entry):
            return self.needs_subcommand()

        kwargs = {}
        for arg in self.annotated:
            kwargs[arg.name] = getattr(args, arg.name, None)

        for additional in self.additional:
            arg = additional.create(rt, args, self)
            kwargs[additional.name] = arg

        result = self.entry(**kwargs)
        return 0 if result is None else result

    @property
    def full_name(self) -> str:
        """Names of all the levels of the command, e.g. ``github matrix``."""
        names: typing.List[str] = []
        current: typing.Optional[Command] = self
        while current is not None:
            if current.name:
                names.append(current.name)
            current = current.parent
        return " ".join(reversed(names))

    def needs_subcommand(self) -> int:
        """
        Report that this command cannot be called on its own, list the known
        subcommands with the first paragraph of their docs and return 1.
        """

        print(
            f"{self.full_name} needs a subcommand; known subcommands are:",
            file=sys.stderr,
        )
        children = sorted(self.children, key=lambda child: child.name)
        name_width = max(len(child.name) for child in children)
        indent = " " * (name_width + 4)
        columns = max(shutil.get_terminal_size().columns - 1, len(indent) + 20)
        for child in children:
            summary = child.doc.split("\n\n")[0]
            line = textwrap.fill(
                f"  {child.name:<{name_width}}  {summary}",
                width=columns,
                subsequent_indent=indent,
            )
            print(line, file=sys.stderr)
        return 1


def _empty_body():
    pass


T = typing.TypeVar("T")


def _first(
    fltr: typing.Callable[[T], bool], items: typing.Iterable[T]
) -> typing.Optional[T]:
    try:
        return next(filter(fltr, items))
    except StopIteration:
        return None


def _argparse_visit_all(
    parser: Parser, cfg: env.FlowConfig, menu: typing.List["Command"]
):
    shortcut_configs = _build_run_shortcuts(cfg)

    parser.menu = menu
    parser.flow = cfg
    parser.shortcuts = shortcut_configs

    subparsers = parser.add_command_subparsers(
        dest="command", metavar="command", help="Known command name, see below"
    )

    subparsers.parent = parser

    run: typing.Optional[Command] = None
    for entry in menu:
        entry.argparse_visit(subparsers)
        if entry.name == "run":
            run = entry

    if run is not None and len(cfg.aliases) > 0:
        commands = {entry.name for entry in menu}
        cfg.aliases = [alias for alias in cfg.aliases if alias.name not in commands]
        for alias in cfg.aliases:
            run.argparse_visit(subparsers, alias=alias.name, doc=alias.doc)
    else:
        cfg.aliases = []

    pass


def _build_menu(cmd: arg._Command, parent: typing.Optional[Command]):
    name = cmd.name
    doc = cmd.doc or ""
    entry = cmd.entry or _empty_body

    args = _extract_args(entry)
    additional = [entry for entry in args if isinstance(entry, AdditionalArgument)]
    annotated = [entry for entry in args if isinstance(entry, AnnotatedArgument)]

    current = Command(
        name=name,
        doc=doc,
        entry=entry,
        annotated=annotated,
        additional=additional,
        parent=parent,
    )
    for child in cmd.subs.values():
        current.children.append(_build_menu(child, current))

    return current


def _extract_arg(argument: _inspect.Argument):
    for ctor in [configs.Configs, env.Runtime, Command]:
        if argument.type is ctor:
            return AdditionalArgument(argument.name, ctor)

    metadata: typing.Optional[arg.Argument] = _first(
        lambda meta: isinstance(meta, arg.Argument), argument.metadata
    )

    if metadata is None or argument.type is None:
        return None

    optional = metadata.opt
    if optional is None:
        NoneType = type(None)
        is_union = typing.get_origin(argument.type) is typing.Union
        optional = is_union and NoneType in typing.get_args(argument.type)
    metadata.opt = optional

    return AnnotatedArgument(argument.name, metadata)


def _extract_args(entry: callable):  # type: ignore
    args_with_possible_nones = map(_extract_arg, _inspect.signature(entry))
    args = filter(lambda item: item is not None, args_with_possible_nones)
    return typing.cast(typing.List[AnyArgument], list(args))


def _build_run_shortcuts(cfg: env.FlowConfig):
    shortcut_configs: typing.Dict[str, typing.List[str]] = {}
    args: typing.List[typing.Tuple[str, typing.List[str], bool, bool]] = []

    shortcuts = cfg.shortcuts
    for shortcut_name in sorted(shortcuts.keys()):
        has_os = False
        has_compiler = False
        shortcut = shortcuts[shortcut_name]
        config: typing.List[str] = []
        for key in sorted(shortcut.keys()):
            has_os = has_os or key == "os"
            has_compiler = has_compiler or key == "compiler"
            value = shortcut[key]
            if isinstance(value, list):
                for v in value:
                    config.append(f"{key}={_shortcut_value(v)}")
            else:
                config.append(f"{key}={_shortcut_value(value)}")
        if len(config) > 0:
            args.append((shortcut_name, config, has_os, has_compiler))

    if len(args):
        os_prefix = f"os={env.platform}"
        compiler_prefix = f"compiler={env.default_compiler()}"

        for shortcut_name, config, has_os, has_compiler in args:
            if not has_compiler:
                config.insert(0, compiler_prefix)
            if not has_os:
                config.insert(0, os_prefix)
            shortcut_configs[shortcut_name] = config

    return shortcut_configs


def _shortcut_value(value) -> str:
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    return str(value)


def _argparse_runtime_visit(parser: Parser):
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="Show this help message and exit",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        required=False,
        help="Print steps and commands, do nothing",
    )

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--silent",
        action="store_true",
        required=False,
        help="Remove most of the output",
    )
    verbosity.add_argument(
        "--verbose",
        action="store_true",
        required=False,
        help="Add even more output",
    )


def _argparse_config_visit(parser: Parser):
    parser.add_argument(
        "-D",
        dest="configs",
        metavar="key=value",
        nargs="*",
        action="store",
        default=[],
        help="Run only builds on matching configs. The key is one of "
        'the keys into "matrix" object in .flow/matrix.yml definition '
        "and the value is one of the possible values for that key. In "
        "case of boolean flags, such as sanitizer, the true value is "
        'one of "true", "on", "yes", "1" and "with-<key>", '
        'i.e. "with-sanitizer" for sanitizer.'
        " "
        "If given key is never used, all values from .flow/matrix.yaml "
        "for that key are used. Otherwise, only values from command "
        "line are used.",
    ).completer = completers.matrix_completer  # type: ignore

    parser.add_argument(
        "-E",
        dest="extra",
        metavar="key=value",
        nargs="*",
        action="store",
        default=[],
        help="After calculating all the matching configs through -D, "
        "extend the configuration with the -E; for each singular name, this "
        "name is simply added to matching configs, for repeating name, a new "
        "cartesian axis for the config is created and the configs are "
        "populated on it.",
    )

    parser.add_argument(
        "--official",
        action="store_true",
        required=False,
        help="Cut matrix to release builds only",
    )

    if len(parser.shortcuts):
        group = parser.add_mutually_exclusive_group()

        for shortcut_name in sorted(parser.shortcuts.keys()):
            config = parser.shortcuts[shortcut_name]
            group.add_argument(
                f"--{shortcut_name}",
                required=False,
                action="store_true",
                help=f'Shortcut for "-D {" ".join(config)}"',
            )


def verbose_info(commands: typing.List[Command], prefix=""):
    """
    Print every command with the function implementing it; used with
    ``--verbose``.

    :param commands: commands to print, with their subcommands
    :param prefix: names of the parent levels
    """
    for command in commands:
        cli = f"{prefix} {command.name}" if prefix else command.name
        if command.entry is not None:
            print(
                f"-- Command: adding `{cli}` from `{command.entry.__module__}.{command.entry.__name__}(...)`"
            )
        verbose_info(command.children, cli)
