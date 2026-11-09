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
class VersionAttribute:
    value: int
    is_max: bool = False
    is_min: bool = False


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


class ExtAttrError(ValueError):
    """Extended attribute used in a way its declared type does not allow."""


ExtAttrMap = dict[str, list[expr.ExtendedAttribute]]
"""Extended attributes of one IDL node, grouped by name in source order."""


def group_extended_attributes(ext_attrs: list[expr.ExtendedAttribute]) -> ExtAttrMap:
    result: ExtAttrMap = {}
    for attr in ext_attrs:
        result.setdefault(attr.name, []).append(attr)
    return result


def _unquote(value: str):
    if value.startswith('"') and value.endswith('"') and len(value) > 1:
        return value[1:-1]
    return value


def _single_extended_attribute(name: str, attributes: ExtAttrMap):
    found = attributes.get(name)
    if not found:
        return None
    if len(found) > 1:
        raise ExtAttrError(f"`{name}' can only be used once")
    return found[0]


def visit_flag_extended_attribute(
    name: str, bag: dict[str, Any], attributes: ExtAttrMap
):
    # Always present, false if absent: a missing key would make Mustache
    # look the name up in outer contexts (e.g. an argument's `ext_attrs.in`
    # found in its operation's `ext_attrs`).
    bag[name] = _single_extended_attribute(name, attributes) is not None


def visit_string_extended_attribute(
    name: str, bag: dict[str, Any], attributes: ExtAttrMap
):
    bag[name] = None
    attr = _single_extended_attribute(name, attributes)
    if attr is None:
        return

    if attr.rhs:
        if isinstance(attr.rhs, expr.LiteralList):
            raise ExtAttrError(
                f"`{name}' takes a single value; declare it as `str-list' to allow more"
            )
        bag[name] = _unquote(cast(str, attr.rhs.value))

    if bag[name] is None:
        del bag[name]


def visit_string_list_extended_attribute(
    name: str, bag: dict[str, Any], attributes: ExtAttrMap
):
    """Collects values from every `name="..."` and `name=("...", ...)`, in order.

    The result is always a list, so templates read the items with `{{.}}`.
    Like `str`, an absent attribute is stored as None, so that templates do
    not pick up a same-named value from an outer scope.

    Next to it, `has_<name>` tells if there are any values, so that templates
    can render a block once, instead of once per item:
    `{{#has_name}}...{{#name}}{{.}}{{/name}}...{{/has_name}}`."""

    bag[name] = None
    values: list[str] = []
    for attr in attributes.get(name, []):
        if attr.rhs is None:
            continue
        if isinstance(attr.rhs, expr.LiteralList):
            values.extend(_unquote(cast(str, item.value)) for item in attr.rhs.value)
        else:
            values.append(_unquote(cast(str, attr.rhs.value)))

    if values:
        bag[name] = values
    bag[has_name(name)] = len(values) > 0


def has_name(name: str):
    return f"has_{name}"


def visit_version_extended_attribute(
    name: str,
    bag: dict[str, Any],
    attributes: ExtAttrMap,
    is_max: bool = False,
    is_min: bool = False,
):
    bag[name] = None
    attr = _single_extended_attribute(name, attributes)
    if attr is None:
        return

    if attr.rhs:
        raw_value = attr.rhs.value
        if not isinstance(raw_value, str):
            return

        try:
            bag[name] = VersionAttribute(
                value=int(raw_value), is_max=is_max, is_min=is_min
            )
        except (TypeError, ValueError):
            return


def flag_extended_attribute(name: str):
    def impl(bag: dict[str, Any], attributes: ExtAttrMap):
        return visit_flag_extended_attribute(name, bag, attributes)

    return impl


def string_extended_attribute(name: str):
    def impl(bag: dict[str, Any], attributes: ExtAttrMap):
        return visit_string_extended_attribute(name, bag, attributes)

    return impl


def string_list_extended_attribute(name: str):
    def impl(bag: dict[str, Any], attributes: ExtAttrMap):
        return visit_string_list_extended_attribute(name, bag, attributes)

    return impl


def version_extended_attribute(name: str, is_max: bool = False, is_min: bool = False):
    def impl(bag: dict[str, Any], attributes: ExtAttrMap):
        return visit_version_extended_attribute(
            name, bag, attributes, is_max=is_max, is_min=is_min
        )

    return impl


ATTR_TYPE = {
    "bool": flag_extended_attribute,
    "str": string_extended_attribute,
    "str-list": string_list_extended_attribute,
    "min-version": lambda name: version_extended_attribute(name, is_min=True),
    "max-version": lambda name: version_extended_attribute(name, is_max=True),
}

GENERIC_WRAPPER = "generic-wrapper"
"""Kind of a `type` extended attribute: `[name] T` is read as `name<T>`.

Declared in the config as `"ext_attrs": {"type": {"name": "generic-wrapper"}}`;
the C++ (or other) name of `name` comes from the types file, like for any other
generic. Allowed only for `type` and the only kind allowed there."""

ExtAttrsVisitor = Callable[[dict[str, Any], ExtAttrMap], None]


@dataclass
class ExtAttrsContextBuilder:
    visitors: dict[str, ExtAttrsVisitor] = field(default_factory=dict)
    applies_to_type: bool = False

    def add_flag(self, name: str):
        self.visitors[name] = flag_extended_attribute(name)

    def add_string(self, name: str):
        self.visitors[name] = string_extended_attribute(name)

    def add_string_list(self, name: str):
        self.visitors[name] = string_list_extended_attribute(name)

    def visit(self, bag: dict[str, Any], attributes: ExtAttrMap):
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

    def string_list(self, name: str):
        self.tgt.add_string_list(name)
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
    generic_wrappers: list[str] = field(default_factory=list)
    """Names of the `generic-wrapper` type attributes, in config order."""

    def from_idl(
        self,
        selector: Callable[["ExtAttrsContextBuilders"], ExtAttrsContextBuilder],
        ext_attrs: list[expr.ExtendedAttribute],
    ):
        result: dict[str, Any] = {}
        attributes = group_extended_attributes(ext_attrs)
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
            generic_wrappers=[
                *self.generic_wrappers,
                *(
                    name
                    for name in rhs.generic_wrappers
                    if name not in self.generic_wrappers
                ),
            ],
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
            ("type", result.type),
        ]
        for key, target in targets:
            group = ext_attrs.get(key, {})
            is_type = key == "type"
            for name, type_name in group.items():
                if is_type != (type_name == GENERIC_WRAPPER):
                    if is_type:
                        message = f"type attributes must be `{GENERIC_WRAPPER}', got `{type_name}' when reading {key}.{name}"
                    else:
                        message = f"only type attributes can be `{GENERIC_WRAPPER}', when reading {key}.{name}"
                    raise RuntimeError(message)
                if is_type:
                    # the flag tells Type.from_idl to wrap the type
                    target.visitors[name] = flag_extended_attribute(name)
                    result.generic_wrappers.append(name)
                    continue
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
                    # flags are always present, so either one being set wins
                    type[key] = bool(type.get(key)) or value
                    continue

                if isinstance(value, str):
                    type[key] = cast(str, type.get(key)) or value
                    continue

                if isinstance(value, list):
                    type[key] = cast(list[str], type.get(key)) or value
                    continue

                if isinstance(value, VersionAttribute):
                    type[key] = cast(VersionAttribute, type.get(key)) or value
                    continue

        # `has_<name>` of a moved str-list follows its list
        for key in self.type.visitors:
            flag = has_name(key)
            if flag in parent:
                del parent[flag]
                type[flag] = bool(type.get(key))

    @staticmethod
    def builtin():
        return ExtAttrsContextBuilders(
            attribute=BuilderBuilder().string("default").build(),
            operation=BuilderBuilder()
            .flag("defaulted")
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
