# Troubleshooting

Common runtime and deployment issues for `let-automation`.

## Related Docs
- Deployment: [DEPLOYMENT.md](DEPLOYMENT.md)
- Discord setup: [examples/discord-webhook-setup.md](examples/discord-webhook-setup.md)

## 1. Common Errors and Fixes

### `ModuleNotFoundError: ...`
Cause: running tests/scripts outside project root or without virtualenv.

Fix:
```bash
cd ~/workspace/let-automation
source .venv/bin/activate
PYTHONPATH=. pytest -q
```

### `python: command not found`
Cause: system only has `python3`.

Fix:
```bash
python3 --version
python3 workflows/auto_sync.py --dry-run
```

### `Webhook not configured` / no Discord messages
Cause: missing `DISCORD_WEBHOOK_URL`.

Fix:
```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python3 workflows/auto_sync.py
```

## 2. Rate Limiting Handling

### Symptoms
- HTTP `429` from Discord or data source
- intermittent failed notifications

### Fixes
- Reduce notification volume:
```bash
export DISCORD_MAX_MESSAGES_PER_RUN=3
```
- Increase delay:
```bash
export DISCORD_RATE_LIMIT_SECONDS=1.0
```
- Retry later for upstream fetch limits; avoid high-frequency polling.

## 3. Excel Generation Issues

### `Permission denied` writing `.xlsx`
Cause: file open in Excel/LibreOffice.

Fix:
- Close workbook and rerun.
- Or run with `--no-backup` if backup path permissions are restricted.

### Corrupted or partially-written workbook
Cause: interrupted process.

Fix:
```bash
# rerun full sync to regenerate output
python3 workflows/auto_sync.py
```

### Date/time format inconsistencies
Cause: mixed timezone input.

Fix:
```bash
export TZ=UTC
python3 workflows/auto_sync.py
```

## 4. Browser/Headless Problems (Spectral Path)

### Browser automation fails in headless/CI
Symptoms: discovery/browser connection errors.

Fix options:
1. Use fallback fetch path (BS4) when spectral is unavailable.
2. Force BS4 explicitly:
```bash
python3 workflows/auto_sync.py --force-bs4
```
3. On CI, use non-browser route unless browser dependencies are fully installed.

### `--force-spectral` fails and exits
Cause: spectral output/discovery unavailable.

Fix:
- Remove `--force-spectral` to allow fallback.
- Validate spectral environment before forcing mode.

## 5. GitHub Actions Failures

### Missing secret errors
Fix:
- Add required repository secrets in Actions settings.

### Workflow works locally but fails on runner
Fix:
- Pin Python version (3.11).
- Use explicit dependency install steps.
- Add debug output (`python --version`, `pip freeze`).

Use [examples/github-actions.yml](examples/github-actions.yml) as reference.
