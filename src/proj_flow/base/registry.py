# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.base.registry** allows building extension points, with ability
to register the plugins with a decorator.
"""

import typing
from collections import OrderedDict

T = typing.TypeVar("T")
K = typing.TypeVar("K")


class Registry(typing.Generic[T]):
    """
    Provides simple registry with the decorator attached to it, which
    implements extension point for plugin system. An extension point is a
    value created from this generic, with extendable interface type as
    the generic argument.

    :param name: name of the extension point, shown in verbose listings

    Known decorators
    ................

    :data:`proj_flow.api.release.project_suites`
        :Argument: :class:`ProjectSuite <proj_flow.api.release.ProjectSuite>`
        :Used by: :func:`proj_flow.api.release.get_project` and
            :func:`proj_flow.log.release.add_release`

        Project version reader and updater, package file name builder.

    :data:`proj_flow.log.release.version_updaters`
        :Argument: :class:`VersionUpdater <proj_flow.log.release.VersionUpdater>`
        :Used by: :func:`proj_flow.log.release.add_release`

        Additional version updaters, for instance, path to schema reference on
        GitHub.

    :data:`proj_flow.log.rich_text.api.changelog_generators`
        :Argument: :class:`ChangelogGenerator <proj_flow.log.rich_text.api.ChangelogGenerator>`
        :Used by: :func:`proj_flow.ext.github.cli.release_cmd`

        Changelog note generator used in CHANGELOG file. Not to confuse with
        generator, which may be used internally by Hosting.add_release.

    :data:`proj_flow.log.commit.hosting_factories`
        :Argument: :class:`HostingFactory <proj_flow.log.commit.HostingFactory>`

        Hosting services, which can recognize a repository by its remotes and
        publish releases there.

    :data:`proj_flow.project.api.project_type`
        :Argument: :class:`ProjectType <proj_flow.project.api.ProjectType>`
        :Used by: :func:`proj_flow.minimal.init.main` and
            :func:`proj_flow.project.api.get_project_type`

        Kinds of projects ``proj-flow init`` can create.

    :data:`proj_flow.ext.sign.api.signing_tool`
        :Argument: :class:`SigningTool <proj_flow.ext.sign.api.SigningTool>`
        :Used by: the Sign and SignPackages steps of :mod:`proj_flow.ext.sign`

        Per-platform code signing tools.

    :data:`proj_flow.ext.webidl.registry.webidl_visitors`
        :Argument: :class:`WebIDLVisitor <proj_flow.ext.webidl.registry.WebIDLVisitor>`
        :Used by: :func:`proj_flow.ext.webidl.model.versioning.load_unversioned_idl`

        Inspectors and modifiers of WebIDL definitions, called after the
        definitions are loaded and before code is generated from them.

    Example
    .......

    .. code-block:: python

        class Animal(ABC):
            @abstractmethod
            def speak(self) -> None: ...

        animals = Registry[Animal]("Animal")

        def speak_all():
            for animal in animals.get():
                animal.speak()

        @animals.add
        class Dog(Animal):
            def speak(self) -> None:
                print("woof!")
    """

    name: str
    container: typing.List[T]

    def __init__(self, name: str):
        self.name = name
        self.container = []
        _debug_copies.append(self)

    def add(self, cls: typing.Type[T]):
        """
        Class decorator registering a plugin. The class is instantiated once,
        without arguments, and the instance is added to the registry.

        :param cls: class implementing the extension point
        :returns: the class itself, unchanged
        """
        obj: T = cls()
        self.container.append(obj)
        return cls

    def get(self):
        """
        :returns: all registered plugin instances, in registration order
        """
        return self.container

    def find(
        self, filter: typing.Callable[[T], K]
    ) -> typing.Tuple[typing.Optional[T], typing.Optional[K]]:
        """
        Find the first plugin, for which the filter returns anything but
        ``None``.

        :param filter: called with each plugin, in registration order
        :returns: the plugin and the value returned by the filter, or
            ``(None, None)``, if no plugin matched
        """
        for item in self.container:
            candidate = filter(item)
            if candidate is not None:
                return item, candidate
        return None, None

    def first(self) -> typing.Optional[T]:
        """
        :returns: the first registered plugin, or ``None``, if there is none
        """
        try:
            return next(self.container.__iter__())
        except StopIteration:
            return None


_debug_copies: typing.List[Registry] = []


def quoted(s: str) -> str:
    """
    Quote a string for the verbose listing: with single quotes, if it
    contains a double quote, with double quotes, if it contains a single
    quote or a space, otherwise not at all.

    :param s: string to quote
    :returns: the string, quoted as needed
    """
    if '"' in s:
        return "'{}'".format(s.replace("\\", r"\\").replace("'", r"\'"))
    if "'" in s or " " in s:
        return '"{}"'.format(s)
    return s


def verbose_info():
    """
    Print every plugin of every registry, with its class and, if present, its
    ``name`` and ``id``; used with ``--verbose``.
    """
    for registry in _debug_copies:
        for item in registry.container:
            full_name = f"{item.__module__}.{item.__class__.__name__}"

            kw = OrderedDict()

            if hasattr(item, "name"):
                kw["name"] = quoted(getattr(item, "name"))
            elif hasattr(item, "__name__"):
                kw["name"] = quoted(getattr(item, "__name__"))

            if hasattr(item, "id"):
                kw["id"] = quoted(getattr(item, "id"))

            items = ", ".join([f"{key}={value}" for key, value in kw.items()])
            if len(items) > 0:
                items = f" ({items})"
            print(f"-- {registry.name}: adding `{full_name}`{items}")
