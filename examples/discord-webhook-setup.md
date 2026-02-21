# Discord Webhook Setup

## 1. Create Webhook
1. Open your Discord server settings.
2. Go to **Integrations -> Webhooks**.
3. Create a webhook and copy the webhook URL.

## 2. Configure Environment Variable

```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/<id>/<token>"
export DISCORD_MAX_MESSAGES_PER_RUN=5
export DISCORD_RATE_LIMIT_SECONDS=0.25
```

## 3. Verify Notification Path

```bash
cd ~/workspace/let-automation
source .venv/bin/activate
PYTHONPATH=. pytest -q tests/test_discord.py
python3 workflows/auto_sync.py --dry-run
```

## 4. Security Notes
- Never commit webhook URLs to git.
- Store production webhook as a CI secret.
- Rotate webhook URL if it leaks.

Back to deployment docs: [DEPLOYMENT.md](../DEPLOYMENT.md)
