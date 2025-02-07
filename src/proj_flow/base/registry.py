# Copyright (c) 2024 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.base.registry**
"""

import typing

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

        animals = Registry[Animal]()

        def speak_all():
            for animal in animals.get():
                animal.speak()

        @animals.add
        class Dog(Animal):
            def speak(self):
                print("woof!")
    """

    _container: typing.List[T] = []

    def add(self, cls: typing.Type[T]):
        obj: T = cls()
        self._container.append(obj)
        return cls

    def get(self):
        return self._container

    def find(
        self, filter: typing.Callable[[T], K]
    ) -> typing.Tuple[typing.Optional[T], typing.Optional[K]]:
        for item in self._container:
            candidate = filter(item)
            if candidate is not None:
                return item, candidate
        return None, None

    def first(self) -> typing.Optional[T]:
        try:
            return next(self._container.__iter__())
        except StopIteration:
            return None
