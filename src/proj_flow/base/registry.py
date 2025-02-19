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

    Known decorators
    ................

    :data:`proj_flow.api.release.project_suites`
        :Argument: :class:`ProjectSuite <proj_flow.api.release.ProjectSuite>`
        :Used by: :func:`src.proj_flow.log.release.add_release`

        Project version reader and updater, package file name builder.

    :data:`proj_flow.log.release.version_updaters`
        :Argument: :class:`VersionUpdaters <proj_flow.api.release.VersionUpdaters>`
        :Used by: :func:`src.proj_flow.log.release.add_release`

        Additional version updaters, for instance, path to schema reference on
        GitHub.

    :data:`proj_flow.log.rich_text.api.changelog_generators`
        :Argument: :class:`ChangelogGenerator <proj_flow.log.rich_text.api.ChangelogGenerator>`
        :Used by: :func:`src.proj_flow.ext.github.cli.release`

        Changelog note generator used in CHANGELOG file. Not to confuse with
        generator, which may be used internally by Hosting.add_release.

    Example
    .......

    .. code-block:: python

        class Animal(ABC)
            @abstractmethod
            def speak(self): ...

        animals = Registry[Animal]("Animal")

        def speak_all():
            for animal in animals.get():
                animal.speak()

        @animals.add
        class Dog(Animal):
            def speak(self):
                print("woof!")
    """

    name: str
    container: typing.List[T]

    def __init__(self, name: str):
        self.name = name
        self.container = []
        _debug_copies.append(self)

    def add(self, cls: typing.Type[T]):
        obj: T = cls()
        self.container.append(obj)
        return cls

    def get(self):
        return self.container

    def find(
        self, filter: typing.Callable[[T], K]
    ) -> typing.Tuple[typing.Optional[T], typing.Optional[K]]:
        for item in self.container:
            candidate = filter(item)
            if candidate is not None:
                return item, candidate
        return None, None

    def first(self) -> typing.Optional[T]:
        try:
            return next(self.container.__iter__())
        except StopIteration:
            return None


_debug_copies: typing.List[Registry] = []


def quoted(s: str) -> str:
    if '"' in s:
        return "'{}'".format(s.replace("\\", r"\\").replace("'", r"\'"))
    if "'" in s or " " in s:
        return '"{}"'.format(s)
    return s


def verbose_info():
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
