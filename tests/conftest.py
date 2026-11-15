"""Shared fixtures; the fakes themselves live in ``fakes.py``."""

import pytest
from fakes import FakeHosting, FakeRuntime


@pytest.fixture
def fake_rt(tmp_path):
    return FakeRuntime(root=tmp_path)


@pytest.fixture
def hosting():
    return FakeHosting()
