"""Runtime configuration for let-automation."""

from __future__ import annotations

import os

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
DISCORD_MAX_MESSAGES_PER_RUN = int(os.getenv("DISCORD_MAX_MESSAGES_PER_RUN", "5"))
DISCORD_RATE_LIMIT_SECONDS = float(os.getenv("DISCORD_RATE_LIMIT_SECONDS", "0.25"))
