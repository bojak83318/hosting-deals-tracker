from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from notifications.email import EmailNotifier


def _deal(price: float | None = 4.0):
    return {
        "thread_id": "123",
        "title": "RackNerd KVM VPS",
        "provider": "RackNerd",
        "category": "VPS",
        "cpu": 2,
        "ram_gb": 4,
        "storage_gb": 80,
        "storage_type": "NVMe",
        "price_monthly": price,
        "price_yearly": None,
        "url": "https://lowendtalk.com/discussion/123",
        "location": "USA",
        "date_fetched": "2026-02-20T18:00:00",
    }


def _notifier(**kwargs) -> EmailNotifier:
    defaults = {
        "smtp_host": "smtp.example.com",
        "from_email": "alerts@example.com",
        "to_email": "ops@example.com",
    }
    defaults.update(kwargs)
    return EmailNotifier(**defaults)


def test_skip_when_smtp_not_fully_configured():
    notifier = EmailNotifier(smtp_host="", from_email="alerts@example.com", to_email="ops@example.com")
    result = notifier.send_deals([_deal()])
    assert result.sent == 0
    assert result.skipped == 1
    assert result.failed == 0


def test_build_subject_body_human_readable():
    notifier = _notifier()
    subject = notifier.build_subject(_deal(price=3.0))
    body = notifier.build_body(_deal(price=3.0))

    assert "[HOT]" in subject
    assert "RackNerd KVM VPS" in subject
    assert "RackNerd" in subject
    assert "$3.00/mo" in subject
    assert "Title: RackNerd KVM VPS" in body
    assert "Provider: RackNerd" in body
    assert "Price: $3.00/mo" in body
    assert "Specs: 2 vCPU, 4 GB RAM, 80 GB NVMe" in body
    assert "URL: https://lowendtalk.com/discussion/123" in body


def test_send_deals_rate_limited_and_capped(monkeypatch):
    calls = {"count": 0, "sleep": 0}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            assert host == "smtp.example.com"
            assert port == 587
            assert timeout == 10

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            return None

        def login(self, username, password):
            return None

        def send_message(self, message):
            calls["count"] += 1
            assert "RackNerd KVM VPS" in message["Subject"]

    def fake_sleep(seconds):
        calls["sleep"] += 1

    monkeypatch.setattr("notifications.email.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr("notifications.email.time.sleep", fake_sleep)

    notifier = _notifier(max_messages_per_run=2, rate_limit_seconds=0.01)
    result = notifier.send_deals([_deal(4), _deal(8), _deal(20)])

    assert calls["count"] == 2
    assert calls["sleep"] == 1
    assert result.sent == 2
    assert result.skipped == 1
    assert result.failed == 0


def test_send_deals_continues_after_per_message_failure(monkeypatch):
    state = {"attempt": 0}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            return None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def starttls(self):
            return None

        def login(self, username, password):
            return None

        def send_message(self, message):
            state["attempt"] += 1
            if state["attempt"] == 1:
                raise RuntimeError("smtp send failed")

    monkeypatch.setattr("notifications.email.smtplib.SMTP", FakeSMTP)
    monkeypatch.setattr("notifications.email.time.sleep", lambda *_: None)

    notifier = _notifier(max_messages_per_run=2)
    result = notifier.send_deals([_deal(4), _deal(8)])

    assert result.sent == 1
    assert result.failed == 1
    assert result.skipped == 0
