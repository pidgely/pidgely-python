from __future__ import annotations

from typing import Iterator, List

import pytest
import respx

import pidgely

API_KEY = "pdg_test_0123456789abcdef"
BASE = "https://api.pidgely.test"


@pytest.fixture
def mock() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=BASE, assert_all_called=False) as router:
        yield router


@pytest.fixture
def sleeps() -> List[float]:
    return []


@pytest.fixture
def client(sleeps: List[float]) -> Iterator[pidgely.Pidgely]:
    c = pidgely.Pidgely(API_KEY, base_url=BASE)
    c._sleep = sleeps.append
    yield c
    c.close()


@pytest.fixture(autouse=True)
def _reset_module(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PIDGELY_API_KEY", raising=False)
    monkeypatch.delenv("PIDGELY_BASE_URL", raising=False)
    monkeypatch.setattr(pidgely, "api_key", None)
    monkeypatch.setattr(pidgely, "base_url", None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
