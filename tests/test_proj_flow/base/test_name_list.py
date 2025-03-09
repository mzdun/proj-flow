# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from proj_flow.base.name_list import name_list


def test_name_list():
    assert name_list([]) == ""
    assert name_list(["first"]) == "first"
    assert name_list(["first", "second"]) == "first and second"
    assert name_list(["first", "second", "third"]) == "first, second and third"
    assert (
        name_list(["first", "second", "third", "fourth", "fifth", "sixth", "seventh"])
        == "first, second, third, fourth, fifth, sixth and seventh"
    )
