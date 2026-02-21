from __future__ import annotations

from notifications.discord import DiscordNotifier


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


def test_skip_when_webhook_not_configured():
    notifier = DiscordNotifier(webhook_url="")
    result = notifier.send_deals([_deal()])
    assert result.sent == 0
    assert result.skipped == 1
    assert result.failed == 0


def test_empty_deals_safe():
    notifier = DiscordNotifier(webhook_url="https://example.com")
    result = notifier.send_deals([])
    assert result.sent == 0
    assert result.skipped == 0
    assert result.failed == 0


def test_build_embed_color_quality_hot_good_info():
    notifier = DiscordNotifier(webhook_url="https://example.com")
    hot = notifier.build_embed(_deal(price=3.0))
    good = notifier.build_embed(_deal(price=9.0))
    info = notifier.build_embed(_deal(price=40.0))

    assert hot["color"] == notifier.HOT_COLOR
    assert good["color"] == notifier.GOOD_COLOR
    assert info["color"] == notifier.NORMAL_COLOR
    assert "RackNerd" in str(hot["fields"])


def test_build_embed_handles_non_dict_and_bad_price_values():
    notifier = DiscordNotifier(webhook_url="https://example.com")
    embed = notifier.build_embed("not-a-dict")
    weird_price = _deal(price=None)
    weird_price["price_monthly"] = "not-a-number"
    weird_embed = notifier.build_embed(weird_price)

    assert embed["title"] == "[INFO] New Deal"
    assert embed["url"] == "https://lowendtalk.com"
    assert weird_embed["color"] == notifier.NORMAL_COLOR
    assert any(field["name"] == "Price" and field["value"] == "N/A" for field in weird_embed["fields"])


def test_send_deals_rate_limited_and_capped(monkeypatch):
    calls = {"count": 0, "sleep": 0}

    class Resp:
        status_code = 204

    def fake_post(url, json, timeout):
        calls["count"] += 1
        assert "embeds" in json
        return Resp()

    def fake_sleep(seconds):
        calls["sleep"] += 1

    monkeypatch.setattr("notifications.discord.requests.post", fake_post)
    monkeypatch.setattr("notifications.discord.time.sleep", fake_sleep)

    notifier = DiscordNotifier("https://example.com/webhook", max_messages_per_run=2, rate_limit_seconds=0.01)
    result = notifier.send_deals([_deal(4), _deal(8), _deal(20)])

    assert calls["count"] == 2
    assert calls["sleep"] == 1
    assert result.sent == 2
    assert result.skipped == 1


def test_send_deals_sleeps_only_between_attempted_sends(monkeypatch):
    calls = {"count": 0, "sleep": 0}

    class Resp:
        status_code = 204

    def fake_post(url, json, timeout):
        calls["count"] += 1
        return Resp()

    def fake_sleep(seconds):
        calls["sleep"] += 1

    monkeypatch.setattr("notifications.discord.requests.post", fake_post)
    monkeypatch.setattr("notifications.discord.time.sleep", fake_sleep)

    notifier = DiscordNotifier("https://example.com/webhook", max_messages_per_run=3, rate_limit_seconds=0.01)
    original_build = notifier.build_embed
    call_count = {"n": 0}

    def flaky_build_embed(deal):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ValueError("bad deal")
        return original_build(deal)

    notifier.build_embed = flaky_build_embed  # type: ignore[method-assign]
    result = notifier.send_deals([_deal(4), _deal(8)])

    assert calls["count"] == 1
    assert calls["sleep"] == 0
    assert result.sent == 1
    assert result.failed == 1


def test_send_deals_handles_non_dict_values(monkeypatch):
    calls = {"count": 0}

    class Resp:
        status_code = 204

    def fake_post(url, json, timeout):
        calls["count"] += 1
        assert "embeds" in json
        return Resp()

    monkeypatch.setattr("notifications.discord.requests.post", fake_post)

    notifier = DiscordNotifier("https://example.com/webhook", max_messages_per_run=3)
    result = notifier.send_deals([None, "bad", _deal(5)])  # type: ignore[list-item]

    assert calls["count"] == 3
    assert result.sent == 3
    assert result.failed == 0


def test_send_deals_handles_failures(monkeypatch):
    class Resp:
        status_code = 500

    monkeypatch.setattr("notifications.discord.requests.post", lambda *a, **k: Resp())
    notifier = DiscordNotifier("https://example.com/webhook", max_messages_per_run=1)
    result = notifier.send_deals([_deal(5)])
    assert result.failed == 1
