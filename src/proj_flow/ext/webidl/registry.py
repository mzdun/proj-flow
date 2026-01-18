# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from abc import ABC
from typing import Any

from pywebidl2 import expr

from proj_flow.base.registry import Registry
from proj_flow.ext.webidl.model.ast import MergedDefinitions


class WebIDLVisitor(ABC):
    def on_definitions(self, definitions: MergedDefinitions): ...


class WebIDLCustomExtAttr(ABC):
    def on_attribute(
        self, name: str, ext_attrs: expr.ExtendedAttribute, result: dict[str, Any]
    ): ...


webidl_visitors = Registry[WebIDLVisitor]("WebIDLVisitor")
