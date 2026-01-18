# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)


from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar, cast

from pywebidl2 import expr, parser, raw_parse, validate

from proj_flow.ext.webidl.base.config import ExtAttrsContextBuilders, TypeReplacement


def _flatten_union(ast: expr.IdlType) -> expr.IdlType:
    arguments = cast(list[expr.IdlType], ast.idl_type)
    result: list[expr.IdlType] = []
    for argument in arguments:
        if not argument.union:
            result.append(argument)
            continue
        argument = _flatten_union(argument)
        if argument.nullable:
            result.append(argument)
        sub_args = cast(list[expr.IdlType], argument.idl_type)
        result.extend(sub_args)
    ast.idl_type = result
    return ast


@dataclass
class TypeVisitor:
    known_types: set[str]
    types: dict[str, TypeReplacement]
    local_references: set[str] = field(default_factory=set)
    modules_or_includes: set[str] = field(default_factory=set)

    def on_type_name(self, type_name: str):
        if type_name in self.known_types:
            self.local_references.add(type_name)
            return type_name

        replacement = self.types.get(type_name)
        if replacement:
            if replacement.module_or_include:
                self.modules_or_includes.add(replacement.module_or_include)
            return replacement.name

        return type_name

    def on_type(self, type: "Type"):
        if type.nullable:
            replacement = self.types.get("optional")
            if replacement and replacement.module_or_include:
                self.modules_or_includes.add(replacement.module_or_include)

        type.name = self.on_type_name(type.idl_name)


@dataclass
class TypeArg:
    arg_type: "Type | expr.IdlType"
    first: bool = False


@dataclass
class Type:
    idl_name: str
    name: str | None = field(default=None)
    arguments: list[TypeArg] = field(default_factory=list)
    nullable: bool = field(default=False)
    generic: bool = field(default=False)
    ext_attrs: dict = field(default_factory=dict)

    def populate_references(self, visitor: TypeVisitor):
        visitor.on_type(self)
        for arg in self.arguments:
            if isinstance(arg.arg_type, Type):
                arg.arg_type.populate_references(visitor)

    def __patched_type(self):
        if self.generic and self.idl_name == "sequence":
            if self.ext_attrs.get("unique"):
                self.idl_name = "set"
            elif self.ext_attrs.get("span"):
                self.idl_name = "span"
        elif self.generic and self.idl_name == "record":
            first_arg = (
                self.arguments[0].arg_type
                if self.arguments and isinstance(self.arguments[0].arg_type, Type)
                else None
            )
            if first_arg:
                first_arg.idl_name = self.ext_attrs.get("key") or "string"
        for attr in ["unique", "span", "key"]:
            if attr in self.ext_attrs:
                del self.ext_attrs[attr]
        return self

    @staticmethod
    def from_idl(
        ast: expr.IdlType,
        builders: ExtAttrsContextBuilders,
        parent_ast_attrs: list[expr.ExtendedAttribute],
    ) -> "Type | expr.IdlType":
        ext_attrs = builders.from_idl(lambda b: b.type, ast.ext_attrs)
        parent_attrs = builders.from_idl(lambda b: b.type, parent_ast_attrs)
        builders.property_fixup(ext_attrs, parent_attrs)
        nullable = ext_attrs.get("nullable", False)
        if "nullable" in ext_attrs:
            del ext_attrs["nullable"]

        if ast.union:
            ast = _flatten_union(ast)
            args = cast(list[expr.IdlType], ast.idl_type)
            arguments = [TypeArg(Type.from_idl(arg, builders, [])) for arg in args]
            if arguments:
                arguments[0].first = True
            return Type(
                idl_name="union",
                arguments=arguments,
                nullable=ast.nullable or nullable,
                generic=True,
                ext_attrs=ext_attrs,
            ).__patched_type()

        if isinstance(ast.idl_type, str):
            return Type(
                idl_name=ast.idl_type,
                nullable=ast.nullable or nullable,
                ext_attrs=ext_attrs,
            ).__patched_type()

        if ast.generic:
            arguments: list[TypeArg] = []
            if isinstance(ast.idl_type, str):
                arguments = [TypeArg(Type(idl_name=ast.idl_type), True)]
            elif isinstance(ast.idl_type, expr.IdlType):
                arguments = [TypeArg(Type.from_idl(ast.idl_type, builders, []), True)]
            else:
                arguments = [
                    TypeArg(Type.from_idl(arg, builders, []))
                    for arg in cast(list[expr.IdlType], ast.idl_type)
                ]
                if arguments:
                    arguments[0].first = True
            return Type(
                idl_name=ast.generic,
                arguments=arguments,
                nullable=ast.nullable or nullable,
                generic=True,
                ext_attrs=ext_attrs,
            ).__patched_type()

        inner = ast.idl_type
        if isinstance(inner, expr.IdlType):
            inner.nullable = inner.nullable or ast.nullable or nullable
            inner.ext_attrs = [*ast.ext_attrs, *inner.ext_attrs]
            inner.generic = inner.generic or ast.generic
            return Type.from_idl(inner, builders, parent_ast_attrs)

        print(type(ast.idl_type), ast.generic != "")
        print(ast)
        return ast


@dataclass
class Attribute:
    name: str
    type: Type | expr.IdlType
    readonly: bool
    static: bool
    ext_attrs: dict

    def populate_references(self, visitor: TypeVisitor):
        if isinstance(self.type, Type):
            self.type.populate_references(visitor)

    @staticmethod
    def from_idl(ast: expr.Attribute, builders: ExtAttrsContextBuilders):
        ext_attrs = builders.from_idl(lambda b: b.attribute, ast.ext_attrs)
        type = Type.from_idl(ast.idl_type, builders, ast.ext_attrs)
        return Attribute(
            name=ast.name,
            type=type,
            readonly=ast.readonly,
            static=ast.special == "static",
            ext_attrs=ext_attrs,
        )


@dataclass
class Constant:
    name: str
    type: Type | expr.IdlType
    value: expr.Expression
    ext_attrs: dict

    def populate_references(self, visitor: TypeVisitor):
        if isinstance(self.type, Type):
            self.type.populate_references(visitor)

    @staticmethod
    def from_idl(ast: expr.Const, builders: ExtAttrsContextBuilders):
        ext_attrs = builders.from_idl(lambda b: b.attribute, ast.ext_attrs)
        type = Type.from_idl(ast.idl_type, builders, ast.ext_attrs)
        return Constant(
            name=ast.name,
            type=type,
            value=ast.value,
            ext_attrs=ext_attrs,
        )


@dataclass
class Argument:
    name: str
    type: Type | expr.IdlType
    ext_attrs: dict
    first: bool = False

    def populate_references(self, visitor: TypeVisitor):
        if isinstance(self.type, Type):
            self.type.populate_references(visitor)

    @staticmethod
    def from_idl(ast: expr.Argument, builders: ExtAttrsContextBuilders):
        ext_attrs = builders.from_idl(lambda b: b.argument, ast.ext_attrs)
        type = Type.from_idl(ast.idl_type, builders, ast.ext_attrs)
        return Argument(
            name=ast.name,
            type=type,
            ext_attrs=ext_attrs,
        )


@dataclass
class Operation:
    name: str
    type: Type | expr.IdlType | None
    arguments: list[Argument]
    static: bool
    ext_attrs: dict

    def populate_references(self, visitor: TypeVisitor):
        if isinstance(self.type, Type):
            self.type.populate_references(visitor)
        for arg in self.arguments:
            arg.populate_references(visitor)

    @staticmethod
    def from_idl(ast: expr.Operation, builders: ExtAttrsContextBuilders):
        ext_attrs = builders.from_idl(lambda b: b.operation, ast.ext_attrs)
        type = (
            Type.from_idl(ast.idl_type, builders, ast.ext_attrs)
            if ast.idl_type
            else None
        )
        arguments = [Argument.from_idl(arg, builders) for arg in ast.arguments]
        if arguments:
            arguments[0].first = True
        return Operation(
            name=ast.name,
            type=type,
            arguments=arguments,
            static=ast.special == "static",
            ext_attrs=ext_attrs,
        )


@dataclass
class MemberContainer:
    constants: list[Constant]
    attributes: list[Attribute]
    operations: list[Operation]

    @staticmethod
    def from_idl(
        ast: expr.Interface | expr.InterfaceMixin, builders: ExtAttrsContextBuilders
    ):
        constants: list[Constant] = []
        attributes: list[Attribute] = []
        operations: list[Operation] = []
        for member in ast.members:
            if isinstance(member, expr.Const):
                constants.append(Constant.from_idl(member, builders))
                continue

            if isinstance(member, expr.Attribute):
                attributes.append(Attribute.from_idl(member, builders))
                continue

            if isinstance(member, expr.Operation):
                operations.append(Operation.from_idl(member, builders))
                continue

            print(f"warning: unsupported member type `{getattr(member, 'type')}'")

        return MemberContainer(
            constants=constants,
            attributes=attributes,
            operations=operations,
        )


def update(existing: dict, incoming: dict):
    for key in incoming:
        val = incoming[key]
        if val or key not in existing:
            existing[key] = val


@dataclass
class Interface:
    name: str
    inheritance: str | None
    partial: bool
    constants: list[Constant]
    attributes: list[Attribute]
    operations: list[Operation]
    ext_attrs: dict
    has_constants: bool = field(default=False)
    has_attributes: bool = field(default=False)
    has_operations: bool = field(default=False)

    def populate_references(self, visitor: TypeVisitor):
        if self.inheritance:
            visitor.on_type_name(self.inheritance)
        for item in self.constants:
            item.populate_references(visitor)
        for item in self.attributes:
            item.populate_references(visitor)
        for item in self.operations:
            item.populate_references(visitor)

    @staticmethod
    def from_idl(ast: expr.Interface, builders: ExtAttrsContextBuilders):
        members = MemberContainer.from_idl(ast, builders)
        return Interface(
            name=ast.name,
            inheritance=ast.inheritance,
            partial=ast.partial,
            constants=members.constants,
            attributes=members.attributes,
            operations=members.operations,
            ext_attrs=builders.from_idl(lambda b: b.interface, ast.ext_attrs),
        )


@dataclass
class InterfaceMixin:
    partial: bool
    constants: list[Constant]
    attributes: list[Attribute]
    operations: list[Operation]
    ext_attrs: dict

    @staticmethod
    def from_idl(ast: expr.InterfaceMixin, builders: ExtAttrsContextBuilders):
        members = MemberContainer.from_idl(ast, builders)
        return InterfaceMixin(
            partial=ast.partial,
            constants=members.constants,
            attributes=members.attributes,
            operations=members.operations,
            ext_attrs=builders.from_idl(lambda b: b.interface, ast.ext_attrs),
        )


@dataclass
class EnumInfo:
    name: str
    NAME: str
    items: list[str]
    ext_attrs: dict

    @staticmethod
    def from_idl(ast: expr.Enum, builders: ExtAttrsContextBuilders):
        return EnumInfo(
            name=ast.name,
            NAME=ast.name.upper(),
            items=[cast(str, value.value) for value in ast.values],
            ext_attrs=builders.from_idl(lambda b: b.enum, ast.ext_attrs),
        )


@dataclass
class MergedDefinitions:
    interfaces: dict[str, Interface] = field(default_factory=dict)
    enum: list[EnumInfo] = field(default_factory=list)

    def order(self, types: dict[str, TypeReplacement]):
        dependency_tree: dict[str, set[str]] = {}
        modules_or_includes: set[str] = set()

        known_names = set[str]()
        known_names.update(item.name for item in self.enum)
        known_names.update(self.interfaces.keys())

        for name, interface in self.interfaces.items():
            visitor = TypeVisitor(known_names, types)
            interface.populate_references(visitor)
            modules_or_includes.update(visitor.modules_or_includes)
            if name in visitor.local_references:
                visitor.local_references.remove(name)
            dependency_tree[name] = visitor.local_references

        order = list[str]()
        while dependency_tree:
            layer = [
                name
                for name in sorted(dependency_tree.keys())
                if not dependency_tree[name]
            ]
            order.extend(layer)

            if not layer:
                for key in dependency_tree:
                    layer.append(key)
                    break

            for key in layer:
                del dependency_tree[key]

            for key in layer:
                for dependencies in dependency_tree.values():
                    if key in dependencies:
                        dependencies.remove(key)

        return ([self.interfaces[key] for key in order], modules_or_includes)


P_ = TypeVar("P_")
AST_ = TypeVar("AST_")


class PartialSetDict[P_, AST_](dict[str, list[P_]]):
    def append(self, name: str, item: AST_, builders: ExtAttrsContextBuilders):
        conv = self.convert(item, builders)
        try:
            self[name].append(conv)
        except KeyError:
            self[name] = [conv]

    def extend(self, additional: dict[str, list[P_]]):
        for name, partials in additional.items():
            try:
                self[name].extend(partials)
            except KeyError:
                self[name] = [*partials]

    def convert(self, item: AST_, builders: ExtAttrsContextBuilders) -> P_: ...


class InterfacePartialSet(PartialSetDict[Interface | str, expr.Interface | str]):
    def convert(self, item: expr.Interface | str, builders: ExtAttrsContextBuilders):
        return item if isinstance(item, str) else Interface.from_idl(item, builders)


class MixinPartialSet(PartialSetDict[InterfaceMixin, expr.InterfaceMixin]):
    def convert(self, item: expr.InterfaceMixin, builders: ExtAttrsContextBuilders):
        return InterfaceMixin.from_idl(item, builders)


@dataclass
class IdlSyntaxError:
    path: str
    error: parser.SyntaxErrorInfo


@dataclass
class Definitions:
    interfaces: InterfacePartialSet = field(default_factory=InterfacePartialSet)
    mixins: MixinPartialSet = field(default_factory=MixinPartialSet)
    enums: list[EnumInfo] = field(default_factory=list)

    @staticmethod
    def from_idl(ast: expr.Definitions, builders: ExtAttrsContextBuilders):
        result = Definitions()

        for definition in ast.definitions:
            if isinstance(definition, expr.Includes):
                result.interfaces.append(
                    definition.target, definition.includes, builders
                )
                continue
            if isinstance(definition, expr.Interface):
                result.interfaces.append(definition.name, definition, builders)
                continue
            if isinstance(definition, expr.InterfaceMixin):
                result.mixins.append(definition.name, definition, builders)
                continue
            if isinstance(definition, expr.Enum):
                result.enums.append(EnumInfo.from_idl(definition, builders))
                continue

        return result

    @staticmethod
    def merge(*partials: "Definitions"):
        intermediate = Definitions()
        for partial in partials:
            intermediate.interfaces.extend(partial.interfaces)
            intermediate.mixins.extend(partial.mixins)
            intermediate.enums.extend(partial.enums)

        interfaces: dict[str, Interface] = {}
        mixins: dict[str, Interface] = {}

        for name, mixin_set in intermediate.mixins.items():
            mixin = Interface(
                name=name,
                inheritance=None,
                partial=True,
                constants=[],
                attributes=[],
                operations=[],
                ext_attrs={},
            )

            for partial in mixin_set:
                mixin.constants.extend(partial.constants)
                mixin.attributes.extend(partial.attributes)
                mixin.operations.extend(partial.operations)
                update(mixin.ext_attrs, partial.ext_attrs)

            mixins[name] = mixin

        for name, interface_set in intermediate.interfaces.items():
            target = Interface(
                name=name,
                inheritance=None,
                partial=False,
                constants=[],
                attributes=[],
                operations=[],
                ext_attrs={},
            )

            for partial in interface_set:
                if isinstance(partial, str):
                    try:
                        partial = mixins[partial]
                    except KeyError:
                        message = f"{name} cannot find {partial} to include"
                        raise RuntimeError(message)

                target.inheritance = target.inheritance or partial.inheritance
                target.constants.extend(partial.constants)
                target.attributes.extend(partial.attributes)
                target.operations.extend(partial.operations)
                update(target.ext_attrs, partial.ext_attrs)

            target.has_constants = len(target.constants) > 0
            target.has_attributes = len(target.attributes) > 0
            target.has_operations = len(target.operations) > 0
            interfaces[name] = target

        return MergedDefinitions(
            interfaces=interfaces,
            enum=intermediate.enums,
        )

    @staticmethod
    def parse_and_merge(
        names: list[str],
        builders: ExtAttrsContextBuilders,
    ):
        partials: list[Definitions] = []
        syntax_errors: list[IdlSyntaxError] = []

        for name in names:
            path = Path(name)
            text = path.read_text(encoding="UTF-8")
            errors = validate(text)
            for error in errors:
                syntax_errors.append(IdlSyntaxError(path=name, error=error))
            if errors:
                continue

            ast = cast(expr.Definitions, raw_parse(text))
            definitions = Definitions.from_idl(ast, builders)
            partials.append(definitions)

        if syntax_errors:
            return syntax_errors
        return Definitions.merge(*partials)
