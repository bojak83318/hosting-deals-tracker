from __future__ import annotations

import smtplib
import time
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any


@dataclass
class EmailNotifyResult:
    sent: int = 0
    skipped: int = 0
    failed: int = 0


class EmailNotifier:
    """Send deal notifications over SMTP email."""

    def __init__(
        self,
        smtp_host: str | None,
        *,
        smtp_port: int = 587,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        from_email: str | None = None,
        to_email: str | list[str] | None = None,
        max_messages_per_run: int = 5,
        rate_limit_seconds: float = 0.25,
        timeout: int = 10,
        use_tls: bool = True,
    ):
        self.smtp_host = (smtp_host or "").strip()
        self.smtp_port = smtp_port
        self.smtp_username = (smtp_username or "").strip()
        self.smtp_password = smtp_password or ""
        self.from_email = (from_email or "").strip()
        self.to_emails = self._parse_recipients(to_email)
        self.max_messages_per_run = max_messages_per_run
        self.rate_limit_seconds = rate_limit_seconds
        self.timeout = timeout
        self.use_tls = use_tls

    @property
    def enabled(self) -> bool:
        return bool(self.smtp_host and self.from_email and self.to_emails)

    def send_deals(self, deals: list[dict[str, Any]]) -> EmailNotifyResult:
        result = EmailNotifyResult()
        if not self.enabled:
            result.skipped = len(deals)
            return result

        send_count = min(len(deals), self.max_messages_per_run)
        for idx, deal in enumerate(deals[:send_count]):
            try:
                subject = self.build_subject(deal)
                body = self.build_body(deal)
                self._send_message(subject=subject, body=body)
                result.sent += 1
            except Exception:
                result.failed += 1

            if idx < send_count - 1:
                time.sleep(self.rate_limit_seconds)

        if len(deals) > self.max_messages_per_run:
            result.skipped += len(deals) - self.max_messages_per_run
        return result

    def build_subject(self, deal: dict[str, Any]) -> str:
        quality = self._quality(deal.get("price_monthly"))
        title = deal.get("title") or "New Deal"
        provider = deal.get("provider") or "Unknown Provider"
        price = self._price_text(deal)
        return f"[{quality}] {title} - {price} ({provider})"

    def build_body(self, deal: dict[str, Any]) -> str:
        title = deal.get("title") or "New Deal"
        provider = deal.get("provider") or "Unknown"
        price = self._price_text(deal)
        url = deal.get("url") or "https://lowendtalk.com"

        cpu = deal.get("cpu") or "-"
        ram = deal.get("ram_gb") or "-"
        storage = deal.get("storage_gb") or "-"
        storage_type = deal.get("storage_type") or ""
        specs = f"{cpu} vCPU, {ram} GB RAM, {storage} GB {storage_type}".strip()

        location = deal.get("location") or "Unknown"
        category = deal.get("category") or "Unknown"
        thread_id = deal.get("thread_id") or "-"

        return (
            "New hot deal detected.\n\n"
            f"Title: {title}\n"
            f"Provider: {provider}\n"
            f"Price: {price}\n"
            f"Specs: {specs}\n"
            f"Category: {category}\n"
            f"Location: {location}\n"
            f"Thread: {thread_id}\n"
            f"URL: {url}\n"
        )

    def _send_message(self, *, subject: str, body: str) -> None:
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.from_email
        message["To"] = ", ".join(self.to_emails)
        message.set_content(body)

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout) as server:
            if self.use_tls:
                server.starttls()
            if self.smtp_username:
                server.login(self.smtp_username, self.smtp_password)
            server.send_message(message)

    def _price_text(self, deal: dict[str, Any]) -> str:
        monthly = deal.get("price_monthly")
        yearly = deal.get("price_yearly")
        if isinstance(monthly, (int, float)):
            return f"${monthly:.2f}/mo"
        if isinstance(yearly, (int, float)):
            return f"${yearly:.2f}/yr"
        return "N/A"

    def _quality(self, price_monthly: Any) -> str:
        if isinstance(price_monthly, (int, float)):
            if price_monthly <= 5:
                return "HOT"
            if price_monthly <= 15:
                return "GOOD"
        return "INFO"

    def _parse_recipients(self, to_email: str | list[str] | None) -> list[str]:
        if isinstance(to_email, list):
            return [item.strip() for item in to_email if item and item.strip()]
        if isinstance(to_email, str):
            return [item.strip() for item in to_email.split(",") if item.strip()]
        return []
