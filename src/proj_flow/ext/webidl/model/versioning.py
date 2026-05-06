# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from pprint import pprint
import sys
from pywebidl2 import expr

from proj_flow.ext.webidl.registry import webidl_visitors
from proj_flow.ext.webidl.base.config import TemplateRule
from proj_flow.ext.webidl.model.ast import (
    Argument,
    Constant,
    Definitions,
    EnumInfo,
    Interface,
    Attribute,
    MergedDefinitions,
    Operation,
    Type,
)
from proj_flow.ext.webidl.model.builders import (
    ExtAttrsContextBuilders,
    VersionAttribute,
)


@dataclass
class VersionedUse:
    version: int
    name: str


class _FindMaxVersion:

    def __init__(self, config_version: int):
        self.value = config_version

    def visit_attrs(self, ext_attrs: dict):
        for value in ext_attrs.values():
            if isinstance(value, VersionAttribute):
                if value.value > self.value:
                    self.value = value.value

    def visit(
        self, item: Interface | EnumInfo | Attribute | Operation | Argument | Type
    ):
        self.visit_attrs(item.ext_attrs)

        if isinstance(item, Interface):
            for member in item.attributes + item.operations:
                self.visit(member)

        if isinstance(item, Attribute) and isinstance(item.type, Type):
            self.visit(item.type)

        if isinstance(item, Operation):
            for argument in item.arguments:
                self.visit(argument)


def find_max_version(definitions: MergedDefinitions, config_version: int) -> int | None:
    visitor = _FindMaxVersion(config_version)
    for collection in [definitions.interfaces.values(), definitions.enum]:
        for item in collection:
            visitor.visit(item)
    return visitor.value or 1


def __version_matches(ext_attrs: dict, version: int, _name: str):
    max_value: int | None = None
    closest_lower: int | None = None
    closest_larger: int | None = None
    for key, value in ext_attrs.items():
        if not isinstance(value, VersionAttribute):
            continue

        next = value.value
        if max_value is None or next > max_value:
            max_value = next

        if value.is_min:
            if value.is_max:
                raise ValueError(
                    f"version {value.value} in {key} cannot be both min and max"
                )
            if value.value > version:
                continue
            if closest_lower is None or closest_lower < value.value:
                closest_lower = value.value
        if value.is_max:
            if value.value < version:
                continue
            if closest_larger is None or closest_larger > value.value:
                closest_larger = value.value

    result = False
    if max_value is None:
        result = True
    if closest_lower is not None or closest_larger is not None:
        result = True

    return result


def __filter_constants_by_version(constants: list[Constant], version: int, iface: str):
    return [
        c
        for c in constants
        if __version_matches(c.ext_attrs, version, f"constant {iface}.{c.name}")
    ]


def __filter_attributes_by_version(
    attributes: list[Attribute], version: int, iface: str
):
    return [
        a
        for a in attributes
        if __version_matches(a.ext_attrs, version, f"attribute {iface}.{a.name}")
    ]


def __filter_op_params_by_version(operation: Operation, version: int, iface: str):
    filtered_args = [
        a
        for a in operation.arguments
        if __version_matches(
            a.ext_attrs, version, f"argument {iface}.{operation.name}.{a.name}"
        )
    ]
    if filtered_args:
        filtered_args[0].first = True
    return Operation(
        name=operation.name,
        type=operation.type,
        arguments=filtered_args,
        static=operation.static,
        ext_attrs=operation.ext_attrs,
    )


def __filter_operations_by_version(
    operations: list[Operation], version: int, iface: str
):
    return [
        __filter_op_params_by_version(o, version, iface)
        for o in operations
        if __version_matches(o.ext_attrs, version, f"def {iface}.{o.name}")
    ]


def __filter_interface_by_version(iface: Interface, version: int, name: str):
    return Interface(
        name=iface.name,
        inheritance=iface.inheritance,
        partial=iface.partial,
        constants=__filter_constants_by_version(iface.constants, version, name),
        attributes=__filter_attributes_by_version(iface.attributes, version, name),
        operations=__filter_operations_by_version(iface.operations, version, name),
        ext_attrs=iface.ext_attrs,
    )


def filter_by_version(definitions: MergedDefinitions, version: int):
    output = MergedDefinitions()
    for key, iface in definitions.interfaces.items():
        if __version_matches(iface.ext_attrs, version, f"interface {key}"):
            # print(f"-- including interface {key}")
            output.interfaces[key] = __filter_interface_by_version(iface, version, key)
    for enum in definitions.enum:
        if __version_matches(enum.ext_attrs, version, f"enum {enum.name}"):
            # print(f"-- including enum {enum.name}")
            output.enum.append(enum)
    return output


def load_unversioned_idl(rule: TemplateRule, ext_attrs: ExtAttrsContextBuilders):
    names = list(map(lambda path: path.as_posix(), rule.inputs))

    try:
        idl = Definitions.parse_and_merge(names, ext_attrs)
    except FileNotFoundError as e:
        p = Path(e.filename)
        print(f"{e.strerror}: {p.as_posix()}")
        sys.exit(1)
    if isinstance(idl, list):
        for error in idl:
            print(f"{error.path}:{error.error}")
        sys.exit(1)

    for visitor in webidl_visitors.get():
        visitor.on_definitions(idl)

    return idl


def load_versions_idl(
    rule: TemplateRule, ext_attrs: ExtAttrsContextBuilders, config_version: int
):
    unversioned_idl = load_unversioned_idl(rule, ext_attrs)
    max_version = find_max_version(unversioned_idl, config_version) or 1
    for version in range(1, max_version + 1):
        yield version


def split_reused_enums(
    current: list[EnumInfo], previous: list[EnumInfo], previous_version: int
):
    curr = {enum.name: enum for enum in current}
    prev = {enum.name: enum for enum in previous}

    result: list[EnumInfo] = []
    use: list[VersionedUse] = []

    for key, current_enum in curr.items():
        if key not in prev:
            result.append(current_enum)
            continue
        previous_enum = prev[key]
        if current_enum == previous_enum:
            use.append(VersionedUse(version=previous_version, name=key))
            continue
        result.append(current_enum)

    return result, use


class __InterfaceVisitor:
    def __init__(self, seen: set[str]):
        self.seen = seen

    def on_interface(self, interface: Interface):
        for attr in interface.attributes:
            if self.on_type(attr.type, f"{interface.name}/{attr.name}"):
                return True

        for op in interface.operations:
            if self.on_type(op.type, f"{interface.name}/{op.name}"):
                return True
            for arg in op.arguments:
                if self.on_type(arg.type, f"{interface.name}/{op.name}.{arg.name}"):
                    return True

        for const in interface.constants:
            if self.on_type(const.type, f"{interface.name}/{const.name}"):
                return True

        return False

    def on_type(self, type: Type | expr.IdlType | None, hint: str):
        if not isinstance(type, Type):
            return False

        # if type.idl_name not in {"string", "void", "unsigned short"}:
        #     print(f'[{hint}] "{type.idl_name}" vs {self.seen}')

        if type.idl_name in self.seen:
            return True

        for arg in type.arguments:
            if self.on_type(arg.arg_type, f"{hint}/{type.idl_name}"):
                return True

        return False


def interface_uses_modified_types(interface: Interface, modified: set[str]):
    return __InterfaceVisitor(modified).on_interface(interface)


def split_reused_interfaces(
    current: list[Interface], previous: list[Interface], previous_version: int
):
    curr = {enum.name: enum for enum in current}
    prev = {enum.name: enum for enum in previous}

    next_layer: dict[str, Interface] = {}
    modified = set[str]()
    for key, current_interface in curr.items():
        if key not in prev:
            modified.add(key)
            continue
        previous_enum = prev[key]
        if current_interface == previous_enum:
            next_layer[key] = current_interface
            continue
        modified.add(key)

    changed = True
    while changed:
        curr = next_layer
        next_layer = {}
        changed = False

        for key, current_interface in curr.items():
            if interface_uses_modified_types(current_interface, modified):
                modified.add(key)
                changed = True
            else:
                next_layer[key] = current_interface

    result = [interface for interface in current if interface.name in modified]
    use = [
        VersionedUse(version=previous_version, name=interface.name)
        for interface in current
        if interface.name not in modified
    ]

    return result, use
