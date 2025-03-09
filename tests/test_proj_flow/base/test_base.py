# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

from proj_flow.base import __cmake_version__, path_get


def test_cmake_version():
    assert __cmake_version__.CMAKE_VERSION == "3.28"


def test_straight_forward():
    value2 = path_get({"key1": "value1", "key2": "value2"}, "key2")
    assert value2 == "value2"


def test_three_levels():
    value2 = path_get({"key1": {"key2": {"key3": "value3"}}}, "key1.key2.key3")
    assert value2 == "value3"


def test_wrong_key():
    value2 = path_get({"key1": {"key2": {"key3": "value3"}}}, "key1.keyTwo.key3")
    assert value2 is None


def test_default():
    value2 = path_get({"key1": {"key2": "not it"}}, "key1.key2.key3", "fallback")
    assert value2 == "fallback"


def test_tuple():
    value2 = path_get(
        {"key1": {"key2": {"key3": ("value3",)}}}, "key1.key2.key3", "fallback"
    )
    assert value2 == ("value3",)


def test_list():
    value2 = path_get({"key1": [{}, {"key3": "value3"}, {}]}, "key1.1.key3", "fallback")
    assert value2 == "value3"


def test_list_non_int():
    value2 = path_get(
        {"key1": [{}, {"key3": "value3"}, {}]}, "key1.key2.key3", "fallback"
    )
    assert value2 == "fallback"


def test_list_out_of_bounds():
    value2 = path_get({"key1": [{}, {"key3": "value3"}, {}]}, "key1.3.key3", "fallback")
    assert value2 == "fallback"
