from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class DiscordNotifyResult:
    sent: int = 0
    skipped: int = 0
    failed: int = 0


class DiscordNotifier:
    """Send new deal notifications to Discord via webhook."""

    HOT_COLOR = 0x2ECC71  # green
    GOOD_COLOR = 0x3498DB  # blue
    NORMAL_COLOR = 0x95A5A6  # gray

    def __init__(
        self,
        webhook_url: str | None,
        *,
        max_messages_per_run: int = 5,
        rate_limit_seconds: float = 0.25,
        timeout: int = 10,
    ):
        self.webhook_url = (webhook_url or "").strip()
        self.max_messages_per_run = max_messages_per_run
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.webhook_url)

    def send_deals(self, deals: list[dict[str, Any]] | None) -> DiscordNotifyResult:
        result = DiscordNotifyResult()
        deals_list = deals or []
        if not self.enabled:
            result.skipped = len(deals_list)
            return result

        attempted_sends = 0
        for deal in deals_list:
            if attempted_sends >= self.max_messages_per_run:
                result.skipped += 1
                continue

            try:
                embed = self.build_embed(deal)
            except Exception:
                result.failed += 1
                continue

            if attempted_sends > 0:
                time.sleep(self.rate_limit_seconds)

            payload = {"embeds": [embed]}
            try:
                resp = requests.post(self.webhook_url, json=payload, timeout=self.timeout)
                attempted_sends += 1
                if 200 <= resp.status_code < 300:
                    result.sent += 1
                else:
                    result.failed += 1
            except Exception:
                attempted_sends += 1
                result.failed += 1

        return result

    def build_embed(self, deal: dict[str, Any] | Any) -> dict[str, Any]:
        deal_dict = deal if isinstance(deal, dict) else {}
        price = self._as_number(deal_dict.get("price_monthly"))
        quality, color = self._quality_and_color(price)
        title = self._as_text(deal_dict.get("title"), "New Deal")
        raw_url = self._as_text(deal_dict.get("url"), "").strip()
        url = raw_url or "https://lowendtalk.com"
        provider = self._as_text(deal_dict.get("provider"), "Unknown")
        category = self._as_text(deal_dict.get("category"), "Unknown")

        specs = (
            f"{self._as_text(deal_dict.get('cpu'), '-')} vCPU | "
            f"{self._as_text(deal_dict.get('ram_gb'), '-')} GB RAM | "
            f"{self._as_text(deal_dict.get('storage_gb'), '-')} GB "
            f"{self._as_text(deal_dict.get('storage_type'), '')}".strip()
        )
        price_text = self._price_text(deal_dict)
        timestamp = (
            deal_dict.get("date_fetched")
            or deal_dict.get("fetch_date")
            or None
        )

        return {
            "title": f"[{quality}] {title}",
            "url": url,
            "color": color,
            "fields": [
                {"name": "Provider", "value": provider, "inline": True},
                {"name": "Category", "value": category, "inline": True},
                {"name": "Price", "value": price_text, "inline": True},
                {"name": "Specs", "value": specs, "inline": False},
                {
                    "name": "Location",
                    "value": self._as_text(deal_dict.get("location"), "Unknown"),
                    "inline": True,
                },
                {
                    "name": "Thread",
                    "value": self._as_text(deal_dict.get("thread_id"), "-"),
                    "inline": True,
                },
            ],
            "footer": {"text": "LET Automation"},
            "timestamp": str(timestamp) if timestamp is not None else None,
        }

    def _price_text(self, deal: dict[str, Any]) -> str:
        monthly = self._as_number(deal.get("price_monthly"))
        yearly = self._as_number(deal.get("price_yearly"))
        if monthly is not None:
            return f"${monthly:.2f}/mo"
        if yearly is not None:
            return f"${yearly:.2f}/yr"
        return "N/A"

    def _quality_and_color(self, price_monthly: Any) -> tuple[str, int]:
        if isinstance(price_monthly, (int, float)):
            if price_monthly <= 5:
                return "HOT", self.HOT_COLOR
            if price_monthly <= 15:
                return "GOOD", self.GOOD_COLOR
        return "INFO", self.NORMAL_COLOR

    def _as_text(self, value: Any, default: str) -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text or default

    def _as_number(self, value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except (TypeError, ValueError):
                return None
        return None
