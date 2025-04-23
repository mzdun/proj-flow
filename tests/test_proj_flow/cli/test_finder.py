# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)


import os

from proj_flow.cli import finder


def prepare_env(comp_line: str | None, comp_point: int | None = None):
    if comp_line is None:
        try:
            del os.environ["_ARGCOMPLETE"]
        except KeyError:
            pass
        try:
            del os.environ["COMP_LINE"]
        except KeyError:
            pass
        try:
            del os.environ["COMP_POINT"]
        except KeyError:
            pass

        return

    comp_point_value = len(comp_line) if comp_point is None else comp_point
    os.environ["_ARGCOMPLETE"] = "true"
    os.environ["COMP_LINE"] = comp_line
    os.environ["COMP_POINT"] = str(comp_point_value)


def test_find_project():
    prepare_env(None)
    assert finder.autocomplete.find_project() == "."

    prepare_env("token token -C new-dir")
    assert finder.autocomplete.find_project() == "."

    prepare_env("-C new-dir")
    assert finder.autocomplete.find_project() == "."

    prepare_env("token token -C new-dir token")
    assert finder.autocomplete.find_project() == "new-dir"

    # cleanup
    prepare_env(None)
