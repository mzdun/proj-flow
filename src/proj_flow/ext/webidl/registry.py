# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.webidl.registry** defines the extension points for visiting merged
WebIDL definitions and for handling custom extended attributes.
"""

from abc import ABC
from typing import Any

from pywebidl2 import expr

from proj_flow.base.registry import Registry
from proj_flow.ext.webidl.model.ast import MergedDefinitions


class WebIDLVisitor(ABC):
    """
    Extension point for inspecting or changing the WebIDL definitions, after
    they are loaded and before code is generated from them; registered with
    :data:`webidl_visitors`.
    """

    def on_definitions(self, definitions: MergedDefinitions) -> None:
        """
        Visit the merged definitions of a template rule.

        :param definitions: definitions loaded from the rule's IDL files
        """
        ...


class WebIDLCustomExtAttr(ABC):
    """
    Handler of a custom extended attribute.
    """

    def on_attribute(
        self, name: str, ext_attrs: expr.ExtendedAttribute, result: dict[str, Any]
    ) -> None:
        """
        Turn the extended attribute into template context values.

        :param name: name of the attribute
        :param ext_attrs: the attribute from the syntax tree
        :param result: context to store the values in
        """
        ...


#: Registry of the WebIDL definition visitors.
webidl_visitors = Registry[WebIDLVisitor]("WebIDLVisitor")
