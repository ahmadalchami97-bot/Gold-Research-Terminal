"""Shared fixtures — all tests run deterministically on the bundled snapshot."""
import os

os.environ.setdefault("DATA_MODE", "demo")  # never touch the network in tests

import pytest

from app.data.providers import demo
from app.engines.snapshot import build_snapshot


@pytest.fixture(scope="session")
def data():
    return demo.load()


@pytest.fixture(scope="session")
def snap(data):
    return build_snapshot(data)
