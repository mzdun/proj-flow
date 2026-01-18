# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)


import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, cast

from pywebidl2 import expr

package_root = Path(__file__).parent.parent

TR = list[str] | str | None


@dataclass
class TypeReplacement:
    name: str
    module_or_include: str | None = None

    @staticmethod
    def load_config(lang: str | None, types: Path | None):
        data = {}
        if lang:
            path = package_root / "data" / "types" / f"{lang}.json"
            with path.open(encoding="utf-8") as lang_file:
                data.update(cast(dict, json.load(lang_file)))

        if types:
            with types.open(encoding="utf-8") as lang_file:
                all_types_data = cast(dict[str, dict], json.load(lang_file))
                if lang:
                    data.update(all_types_data.get(lang, {}))
                else:
                    data.update(all_types_data.get("", {}))

        result: dict[str, TypeReplacement] = {}
        for key, value in data.items():
            if value is None:
                result[key] = TypeReplacement(name=key)

            elif isinstance(value, str):
                result[key] = TypeReplacement(name=value)

            elif isinstance(value, list) and len(value) == 2:
                mod, name = value
                if isinstance(name, str) and (mod is None or isinstance(mod, str)):
                    result[key] = TypeReplacement(name=name, module_or_include=mod)

        return result


def visit_flag_extended_attribute(
    name: str, bag: dict[str, Any], attributes: dict[str, expr.ExtendedAttribute]
):
    bag[name] = attributes.get(name) != None


def visit_string_extended_attribute(
    name: str, bag: dict[str, Any], attributes: dict[str, expr.ExtendedAttribute]
):
    bag[name] = None
    try:
        attr = attributes[name]
    except KeyError:
        return

    if attr.rhs:
        bag[name] = cast(str, attr.rhs.value)


def flag_extended_attribute(name: str):
    def impl(bag: dict[str, Any], attributes: dict[str, expr.ExtendedAttribute]):
        return visit_flag_extended_attribute(name, bag, attributes)

    return impl


def string_extended_attribute(name: str):
    def impl(bag: dict[str, Any], attributes: dict[str, expr.ExtendedAttribute]):
        return visit_string_extended_attribute(name, bag, attributes)

    return impl


ATTR_TYPE = {
    "bool": flag_extended_attribute,
    "str": string_extended_attribute,
}

ExtAttrsVisitor = Callable[[dict[str, Any], dict[str, expr.ExtendedAttribute]], None]


@dataclass
class ExtAttrsContextBuilder:
    visitors: dict[str, ExtAttrsVisitor] = field(default_factory=dict)
    applies_to_type: bool = False

    def add_flag(self, name: str):
        self.visitors[name] = flag_extended_attribute(name)

    def add_string(self, name: str):
        self.visitors[name] = string_extended_attribute(name)

    def visit(self, bag: dict[str, Any], attributes: dict[str, expr.ExtendedAttribute]):
        for visitor in self.visitors.values():
            visitor(bag, attributes)

    def merge(self, rhs: "ExtAttrsContextBuilder"):
        left = copy.deepcopy(self.visitors)
        right = copy.deepcopy(rhs.visitors)
        left.update(right)
        return ExtAttrsContextBuilder(
            visitors=left,
            applies_to_type=self.applies_to_type,
        )


class BuilderBuilder:
    tgt: ExtAttrsContextBuilder

    def __init__(self, applies_to_type: bool = False):
        self.tgt = ExtAttrsContextBuilder(applies_to_type=applies_to_type)

    def flag(self, name: str):
        self.tgt.add_flag(name)
        return self

    def string(self, name: str):
        self.tgt.add_string(name)
        return self

    def build(self):
        return self.tgt


@dataclass
class ExtAttrsContextBuilders:
    enum: ExtAttrsContextBuilder = field(default_factory=ExtAttrsContextBuilder)
    interface: ExtAttrsContextBuilder = field(default_factory=ExtAttrsContextBuilder)
    attribute: ExtAttrsContextBuilder = field(default_factory=ExtAttrsContextBuilder)
    operation: ExtAttrsContextBuilder = field(default_factory=ExtAttrsContextBuilder)
    return_type: ExtAttrsContextBuilder = field(default_factory=ExtAttrsContextBuilder)
    argument: ExtAttrsContextBuilder = field(default_factory=ExtAttrsContextBuilder)
    type: ExtAttrsContextBuilder = field(default_factory=ExtAttrsContextBuilder)

    def from_idl(
        self,
        selector: Callable[["ExtAttrsContextBuilders"], ExtAttrsContextBuilder],
        ext_attrs: list[expr.ExtendedAttribute],
    ):
        result: dict[str, Any] = {}
        attributes = {attr.name: attr for attr in ext_attrs}
        builder = selector(self)
        builder.visit(result, attributes)
        if builder.applies_to_type:
            self.type.visit(result, attributes)
        return result

    def merge(self, rhs: "ExtAttrsContextBuilders"):
        return ExtAttrsContextBuilders(
            enum=self.enum.merge(rhs.enum),
            interface=self.interface.merge(rhs.interface),
            attribute=self.attribute.merge(rhs.attribute),
            operation=self.operation.merge(rhs.operation),
            return_type=self.return_type.merge(rhs.return_type),
            argument=self.argument.merge(rhs.argument),
            type=self.type.merge(rhs.type),
        )

    @staticmethod
    def from_config(data: dict):
        ext_attrs = cast(dict[str, dict[str, str]], data.get("ext_attrs", {}))
        result = ExtAttrsContextBuilders()
        targets = [
            ("enum", result.enum),
            ("interface", result.interface),
            ("attribute", result.attribute),
            ("operation", result.operation),
            ("return_type", result.return_type),
            ("argument", result.argument),
        ]
        for key, target in targets:
            group = ext_attrs.get(key, {})
            for name, type_name in group.items():
                ctor = ATTR_TYPE.get(type_name)
                if not ctor:
                    message = f"unknown user-defined extended attribute `{type_name}' when reading {key}.{name}"
                    raise RuntimeError(message)
                target.visitors[name] = ctor(name)
        return result

    def property_fixup(self, type: dict[str, Any], parent: dict[str, Any]):
        for key in self.type.visitors:
            if key in parent:
                value = parent[key]
                del parent[key]
                if isinstance(value, bool):
                    type[key] = cast(bool, type.get(key, False)) or value
                    continue

                if isinstance(value, str):
                    type[key] = cast(str, type.get(key, False)) or value
                    continue

    @staticmethod
    def builtin():
        return ExtAttrsContextBuilders(
            attribute=BuilderBuilder().string("default").build(),
            operation=BuilderBuilder()
            .flag("in")
            .flag("out")
            .flag("mutable")
            .flag("throws")
            .build(),
            argument=BuilderBuilder()
            .flag("defaulted")
            .string("default")
            .flag("in")
            .flag("out")
            .build(),
            type=BuilderBuilder()
            .flag("unique")
            .flag("span")
            .flag("nullable")
            .string("key")
            .build(),
        )
