# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

import io
from abc import ABC, abstractmethod

from proj_flow.base import registry

registry._debug_copies = []


class Animal(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def speak(self) -> str: ...


animals = registry.Registry[Animal]("Animal")


@animals.add
class Cat(Animal):
    @property
    def name(self):
        return "Milo"

    def speak(self):
        return "meow!"


@animals.add
class Dog(Animal):
    @property
    def id(self):
        return "good boy"

    @property
    def name(self):
        return "Finn"

    def speak(self):
        return "woof!"


class NamedThing:  # pylint: disable=too-few-public-methods
    __name__: str

    def __init__(self, name: str):
        self.__name__ = name


named_things = registry.Registry[NamedThing]("NamedThing")


@named_things.add
class AThing(NamedThing):  # pylint: disable=too-few-public-methods
    def __init__(self):
        super().__init__('this is a "string"')


empty_registry = registry.Registry[NamedThing]("NamedThing")


def test_registry_verbose_info():
    file = io.StringIO()
    registry.verbose_info(file)
    assert (
        file.getvalue()
        == "-- Animal: adding `test_proj_flow.base.test_registry.Cat` (name=Milo)\n"
        '-- Animal: adding `test_proj_flow.base.test_registry.Dog` (name=Finn, id="good boy")\n'
        "-- NamedThing: adding `test_proj_flow.base.test_registry.AThing` (name='this is a \"string\"')\n"
        # '-- ProjectType: adding `proj_flow.project.cplusplus.project.CPlusPlus` (name="C++ plus CMake plus Conan", id=cxx)\n'
        # "-- HostingFactory: adding `proj_flow.ext.github.hosting.Plugin`\n"
        # "-- ChangelogGenerator: adding `proj_flow.ext.re_structured_changelog.Plugin`\n"
        # "-- VersionUpdater: adding `proj_flow.minimal.ext.bug_report.VersionUpdater`\n"
    )

    def wrap(animal: Animal, name: str):
        return animal if animal.name == name else None

    finn, _finn = animals.find(lambda animal: wrap(animal, "Finn"))
    milo, _milo = animals.find(lambda animal: wrap(animal, "Milo"))
    bella, _bella = animals.find(lambda animal: wrap(animal, "Bella"))
    sounds = [animal.speak() for animal in animals.get()]

    assert finn is not None
    assert milo is not None
    assert bella is None
    assert _bella is None
    assert milo is _milo
    assert finn is _finn
    assert milo is not finn
    assert finn is not animals.first()
    assert milo is animals.first()
    assert sounds == ["meow!", "woof!"]
    assert empty_registry.first() is None
