# Copyright (c) 2026 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from proj_flow.ext.webidl.cli.cmake import cmake
from proj_flow.ext.webidl.cli.depfile import depfile
from proj_flow.ext.webidl.cli.gen import gen
from proj_flow.ext.webidl.cli.init import init
from proj_flow.ext.webidl.cli.root import webidl

__all__ = ["webidl", "init", "cmake", "depfile", "gen"]
