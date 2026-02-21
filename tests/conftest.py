from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class MockResponse:
    def __init__(self, status_code: int = 200, text: str = "", content: bytes | None = None):
        self.status_code = status_code
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError(f"{self.status_code} error")


@pytest.fixture
def fixture_text() -> Any:
    def _load(name: str) -> str:
        return (FIXTURES_DIR / name).read_text(encoding="utf-8")

    return _load


@pytest.fixture
def fixture_bytes() -> Any:
    def _load(name: str) -> bytes:
        return (FIXTURES_DIR / name).read_bytes()

    return _load


@pytest.fixture
def sample_deals() -> list[dict[str, Any]]:
    return [
        {
            "thread_id": "12345",
            "title": "RackNerd KVM VPS",
            "url": "https://lowendtalk.com/discussion/12345/racknerd-offer",
            "author": "RackNerd",
            "date": "2026-02-20T10:00:00+0000",
            "description": "2 vCPU 4GB RAM",
        },
        {
            "thread_id": "12345",
            "title": "RackNerd KVM VPS",
            "url": "https://lowendtalk.com/discussion/12345/racknerd-offer",
            "author": "RackNerd",
            "date": "2026-02-20T10:00:00+0000",
            "description": "duplicate entry",
        },
        {
            "thread_id": "54321",
            "title": "HostHatch Storage VPS",
            "url": "https://lowendtalk.com/discussion/54321/hosthatch-storage",
            "author": "HostHatch",
            "date": "2026-02-19T08:00:00+0000",
            "description": "1TB HDD",
        },
    ]


@pytest.fixture(autouse=True)
def block_real_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Block network by default; tests must explicitly patch session.get."""

    def _blocked(*args: Any, **kwargs: Any):
        raise AssertionError("Real network call blocked in unit tests")

    monkeypatch.setattr("requests.sessions.Session.request", _blocked)
