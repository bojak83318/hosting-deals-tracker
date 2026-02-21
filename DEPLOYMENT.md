# Deployment Guide

This guide covers local deployment, optional Docker deployment, and GitHub Actions cloud runs.

## Related Docs
- Troubleshooting: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Daily scheduler example: [examples/crontab.txt](examples/crontab.txt)
- Full CI/CD example: [examples/github-actions.yml](examples/github-actions.yml)
- Discord webhook setup: [examples/discord-webhook-setup.md](examples/discord-webhook-setup.md)

## 1. Local Installation

### Prerequisites
- Linux/macOS/WSL (Windows supported via PowerShell workflow)
- Python 3.11+
- `pip`

### Steps
```bash
cd ~/workspace/let-automation
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt || pip install requests beautifulsoup4 openpyxl pandas flask pytest

# optional CLI symlink
chmod +x let-automation
ln -sf "$(pwd)/let-automation" ~/bin/let-automation
```

### First Run
```bash
# preview only
let-automation sync --dry-run

# full run
let-automation sync
```

## 2. Optional Docker Setup

If you prefer containerized execution:

```bash
cd ~/workspace/let-automation
cat > Dockerfile <<'DOCKER'
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --upgrade pip && \
    (pip install -r requirements.txt || pip install requests beautifulsoup4 openpyxl pandas flask)
CMD ["python3", "workflows/auto_sync.py"]
DOCKER

docker build -t let-automation:latest .
docker run --rm \
  -e DISCORD_WEBHOOK_URL="$DISCORD_WEBHOOK_URL" \
  -e GITHUB_TOKEN="$GITHUB_TOKEN" \
  -e GITHUB_REPO="$GITHUB_REPO" \
  let-automation:latest
```

## 3. GitHub Actions Cloud Run Setup

### Files
- Existing cloud run workflow: `.github/workflows/cloud-run.yml`
- Example end-to-end workflow: [examples/github-actions.yml](examples/github-actions.yml)

### Repository Setup
1. Push this repository to GitHub.
2. In **Settings -> Secrets and variables -> Actions**, set required secrets.
3. Trigger from **Actions** tab or via API dispatch.

### Typical Triggers
- `workflow_dispatch`: manual run button
- `schedule`: recurring runs
- `repository_dispatch`: external trigger/button

## 4. Environment Variables Reference

### Core Runtime
- `DISCORD_WEBHOOK_URL`: Discord incoming webhook URL
- `DISCORD_MAX_MESSAGES_PER_RUN`: max Discord messages per run (default `5`)
- `DISCORD_RATE_LIMIT_SECONDS`: pause between Discord messages (default `0.25`)

### GitHub Sync/Automation
- `GITHUB_TOKEN`: personal access token or workflow token
- `GITHUB_REPO`: `owner/repo` target for upload/sync

### Router / Optional LLM
- `OPENAI_API_KEY`: required if router provider uses OpenAI
- `CLAUDE_API_KEY`: required if router provider uses Claude

### Optional Execution Tuning
- `PYTHONUNBUFFERED=1`: real-time logs in CI
- `TZ=UTC`: enforce deterministic timestamps in automation

## 5. Scheduling

- Cron example: [examples/crontab.txt](examples/crontab.txt)
- GitHub Actions schedule example: [examples/github-actions.yml](examples/github-actions.yml)

## 6. Verification Checklist

```bash
# local smoke tests
PYTHONPATH=. pytest -q tests/test_email.py tests/test_discord.py tests/test_ml_extractor.py

# dry-run pipeline
python3 workflows/auto_sync.py --dry-run
```

If you hit issues, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
