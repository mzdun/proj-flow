# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.api.arg** is used by various commands to declare CLI arguments.
"""

import argparse
import inspect
import typing
from dataclasses import dataclass, field

from proj_flow.base import inspect as _inspect

T = typing.TypeVar("T")
LazyArgument = typing.Union[T, typing.Callable[[], T]]


def _eval(arg: LazyArgument[T]) -> T:
    if callable(arg):
        return typing.cast(T, arg())
    return arg


class _Completable(typing.Protocol):
    completer: _inspect.Function


@dataclass
class ExclusiveArgumentGroup:
    """
    Group of mutually exclusive arguments. Share one instance in the
    :attr:`Argument.group` of all arguments of the group.
    """

    #: The group is optional; otherwise, one of its arguments is required.
    opt: bool = False

    def visit(self, parser: argparse._ActionsContainer) -> argparse._ActionsContainer:
        """
        Add the group to the parser.

        :param parser: parser or argument group to add to
        :returns: the new group, to add the arguments to
        """
        self.opt
        return parser.add_mutually_exclusive_group(required=not self.opt)


@dataclass
class Argument:
    """
    Command-line argument of an :func:`@arg.command() <command>` function,
    attached to its parameter with ``typing.Annotated[T, Argument(...)]``.
    The parsed value is passed to the parameter of the same name. Most
    fields can also be functions, called when the parser is built.
    """

    #: Help text of the argument; also used in the generated docs.
    help: LazyArgument[str] = ""

    #: The argument is positional.
    pos: bool = False

    #: Option names, e.g. ``["-s", "--steps"]``; when empty, the option is
    #: ``--<parameter name>``. Ignored for positional arguments.
    names: LazyArgument[typing.List[str]] = field(default_factory=list)

    #: Number of values, as in :py:meth:`argparse.ArgumentParser.add_argument`.
    #: Ignored for positional arguments, which take ``"?"`` or ``1``,
    #: depending on :attr:`opt`.
    nargs: LazyArgument[typing.Union[str, int, None]] = None

    #: The argument is optional; when ``None``, it is optional, if the
    #: parameter type is ``Optional[...]``.
    opt: LazyArgument[typing.Optional[bool]] = None

    #: Name of the value in help (``metavar``).
    meta: LazyArgument[typing.Optional[str]] = None

    #: Action, as in :py:meth:`argparse.ArgumentParser.add_argument`.
    action: LazyArgument[typing.Union[str, argparse.Action, None]] = None

    #: Value used, when the argument is missing.
    default: LazyArgument[typing.Optional[typing.Any]] = None

    #: Allowed values.
    choices: LazyArgument[typing.Optional[typing.List[str]]] = None

    #: :py:mod:`argcomplete` completer, e.g. one from
    #: :mod:`proj_flow.api.completers`.
    completer: typing.Optional[_inspect.Function] = None

    #: Mutually exclusive group the argument belongs to.
    group: typing.Optional[ExclusiveArgumentGroup] = None

    def visit(self, parser: argparse._ActionsContainer, name: str):
        """
        Add the argument to the parser.

        :param parser: parser or argument group to add to
        :param name: name of the function parameter, used as ``dest`` and as
            the default option name
        :returns: the new :py:class:`argparse.Action`
        """
        kwargs = {}

        self_help = _eval(self.help)
        self_names = _eval(self.names)
        self_nargs = _eval(self.nargs)
        self_opt = _eval(self.opt)
        self_meta = _eval(self.meta)
        self_action = _eval(self.action)
        self_default = _eval(self.default)
        self_choices = _eval(self.choices)

        if self_help is not None:
            kwargs["help"] = self_help
        if self_nargs is not None:
            kwargs["nargs"] = self_nargs
        if self_meta is not None:
            kwargs["metavar"] = self_meta
        if self_default is not None:
            kwargs["default"] = self_default
        if self_action is not None:
            kwargs["action"] = self_action
        if self_choices is not None:
            kwargs["choices"] = self_choices

        names = (
            [name] if self.pos else self_names if len(self_names) > 0 else [f"--{name}"]
        )

        if self.pos:
            # a required positional without nargs takes a single value, not
            # a one-element list
            if self_nargs is None and self_opt:
                kwargs["nargs"] = "?"
        else:
            kwargs["dest"] = name
            kwargs["required"] = not self_opt

        action = parser.add_argument(*names, **kwargs)
        if self.completer:
            typing.cast(_Completable, action).completer = self.completer

        return action


class FlagArgument(Argument):
    """
    Boolean switch, off by default and turned on by its presence on the
    command line.

    :param help: help text of the switch
    :param names: option names, e.g. ``["-f", "--force"]``; when empty, the
        name is derived from the parameter name
    :param group: mutually exclusive group the switch belongs to
    """

    def __init__(
        self,
        help: str = "",
        names: typing.List[str] = [],
        group: typing.Optional[ExclusiveArgumentGroup] = None,
    ):
        super().__init__(
            help=help,
            names=names,
            group=group,
            opt=True,
            action="store_true",
            default=False,
        )


@dataclass
class _Command:
    name: str
    entry: typing.Optional[_inspect.Function]
    doc: typing.Optional[str]
    subs: typing.Dict[str, "_Command"]

    def add(
        self,
        names: typing.List[str],
        entry: _inspect.Function,
        doc: typing.Optional[str],
    ):
        name = names[0]
        rest = names[1:]
        if len(rest):
            try:
                child = self.subs[name]
            except KeyError:
                child = _Command(name, None, None, {})
                self.subs[name] = child

            return child.add(rest, entry, doc)

        try:
            child = self.subs[name]
            child.entry = entry
            child.doc = doc
        except KeyError:
            child = _Command(name, entry, doc, {})
            self.subs[name] = child
        return child

    def find(self, names: typing.List[str]) -> typing.Optional["_Command"]:
        current: typing.Optional[_Command] = self
        for name in names:
            if current is None:
                return None
            current = current.subs.get(name)
        return current

    def needs_subcommand(self) -> bool:
        return (
            self.entry is not None
            and len(self.subs) > 0
            and _inspect.has_empty_body(self.entry)
        )

    def update_docstring(self, names: typing.List[str]):
        if self.entry is None:
            return

        call = " ".join(names)
        if self.needs_subcommand():
            call += " <subcommand>"

        doc = self.doc or ""
        if doc:
            doc += "\n\n"
        doc += f":call: ``proj-flow {call}``\n\n"
        doc += f":call: ``./flow {call}``\n\n"

        for arg in _inspect.signature(self.entry):
            help = ""
            for meta in arg.metadata:
                if isinstance(meta, Argument):
                    help = meta.help
                    if help:
                        break

            if not help:
                full_name = f"{arg.type.__module__}.{arg.type.__name__}"
                help = _autodoc.get(full_name, "")

            doc += f":param {_doc_type_name(arg.type)} {arg.name}: {help}\n"

        self.entry.__doc__ = doc


_known_commands = _Command("", None, None, {})
_autodoc = {
    "proj_flow.flow.configs.Configs": "Current configuration list.",
    "proj_flow.api.env.Runtime": "Message printer and tools runner respecting ``--dry-run``, ``--silent`` and ``--verbose``.",
    "proj_flow.cli.argument.Command": "The Command object attached to this @command function.",
}


def _doc_type_name(t: type) -> str:
    # Fully qualify project classes, so Sphinx can resolve the reference even
    # if the short name is ambiguous; the ``~`` keeps it rendered short.
    if isinstance(t, type) and t.__module__ != "builtins":
        return f"~{t.__module__}.{t.__qualname__}"
    return _inspect.type_name(t)


def command(*name: str):
    """
    Decorator registering a function as a ``proj-flow`` command. Each name
    is a level of the command, e.g. ``@command("github", "matrix")`` adds
    ``proj-flow github matrix``; the docstring becomes the help of the
    command.

    The parameters of the function decide its arguments:

    - ``Annotated[T, Argument(...)]`` declares a command-line argument;
    - :class:`proj_flow.api.env.Runtime`, :class:`proj_flow.flow.configs.Configs`
      and :class:`proj_flow.cli.argument.Command` are passed in by the
      runner;
    - other parameters are not passed, so they need default values.

    A command with subcommands and an empty body (only a docstring,
    ``pass`` or ``...``) requires one of its subcommands. The function
    returns an exit code; ``None`` means ``0``.

    The decorator also extends the docstring with the calling syntax and
    the parameter descriptions for the API documentation.

    :param name: names of the command levels
    :returns: decorator returning the function unchanged
    """

    def wrap(function: object):
        entry = typing.cast(_inspect.Function, function)
        global _known_commands
        orig_doc = inspect.getdoc(entry)
        names = list(name)
        node = _known_commands.add(names, entry, orig_doc)
        node.update_docstring(names)

        # A new child may turn an already documented, empty-bodied parent
        # into one, which needs a subcommand.
        parent = _known_commands.find(names[:-1])
        if parent is not None and parent is not _known_commands:
            parent.update_docstring(names[:-1])

        return entry

    return wrap


def get_commands():
    """
    Get the tree of registered commands; used by the CLI to build its
    parser.

    :returns: unnamed root of the tree
    """
    return _known_commands
