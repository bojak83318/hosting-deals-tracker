# Codex Task: Implement Spectral-to-Excel Pipeline

> Task ID: spectral-to-excel-pipeline
> Priority: HIGH
> Status: READY

---

## TASK: Replace RSS/BS4 Fetcher with Spectral-Discovered API

Implement a new data extractor that reads from spectral-discovered OpenAPI specs instead of HTML scraping, making spectral the primary data source for Excel generation.

---

## CONTEXT

### Current Pipeline (RSS/BS4):
```
router -> spectral (discovery only, unused for data)
       -> let_api_fetcher.py (HTML/RSS + bs4) 
       -> auto_sync.py
       -> excel
```

### Target Pipeline (Spectral API):
```
router -> spectral-nodriver (captures API calls)
       -> spectral analyze (generates api.yaml + client)
       -> NEW: spectral_deals_extractor.py (reads spec/client)
       -> auto_sync.py
       -> excel
```

### Files Involved:
- **Source**: `workspace/spectral-nodriver/spectral_nodriver.py` (capture/analyze)
- **Source**: `workspace/let-automation/spectral-bridge/let_spectral.py` (discover, analyze, client)
- **Output**: `~/.spectral-nodriver/output/lowendtalk_com_*/api.yaml` (OpenAPI spec)
- **Output**: `~/.spectral-nodriver/output/lowendtalk_com_*/*_automation.py` (generated client)
- **Current Fetcher**: `workspace/let-automation/fetcher/let_api_fetcher.py` (to be replaced/augmented)
- **Orchestrator**: `workspace/let-automation/workflows/auto_sync.py` (needs modification)

---

## REQUIREMENTS

### 1. Create `extractor/spectral_deals_extractor.py`

**Purpose**: Read spectral output and extract normalized deal rows

**Input Sources** (try in order):
1. Generated Python client (`*_automation.py`)
2. OpenAPI spec (`api.yaml`)
3. Fallback: Direct JSON from captured traffic

**Output Format**:
```python
{
    "thread_id": str,
    "title": str,
    "author": str,
    "post_date": str,
    "url": str,
    "provider": str,
    "category": str,
    "cpu": int | None,
    "ram_gb": float | None,
    "storage_gb": float | None,
    "storage_type": str | None,
    "bandwidth": int | None,
    "ipv4_count": int,
    "ipv6": bool,
    "price_monthly": float | None,
    "price_yearly": float | None,
    "location": str | None,
    "status": "NEW" | "ACTIVE" | "EXPIRED",
    "content_preview": str,
}
```

**Implementation Steps**:
1. Find latest spectral output in `~/.spectral-nodriver/output/`
2. Try to import and use generated client
3. If client fails, parse `api.yaml` directly
4. Map spectral endpoints to deal extraction:
   - GET `/discussions` → list of discussions
   - GET `/discussion/{id}` → discussion details
   - GET `/comments` → comments/content
5. Transform API response to deal schema
6. Apply same spec extraction regex patterns from `let_api_fetcher.py`

### 2. Modify `workflows/auto_sync.py`

**Current `_step_fetch` method**:
```python
def _run_let_scraper(self, ...):
    # Uses let_api_fetcher.py (HTML/BS4)
```

**New Logic**:
```python
def _run_spectral_extraction(self, ...):
    # 1. Check for spectral output
    # 2. If exists: use spectral_deals_extractor.py
    # 3. If not exists or fails: fall back to let_api_fetcher.py
    # 4. Log which source was used
```

**Steps**:
1. Add new step type: `"spectral_extract"`
2. Try spectral first, fallback to BS4
3. Add `--force-spectral` CLI flag
4. Add `--force-bs4` CLI flag
5. Default: try spectral, fall back to BS4

### 3. Update `spectral-bridge/let_spectral.py`

**Add new command**:
```bash
python let_spectral.py extract-to-json
```

**Implementation**:
1. Run spectral discovery if no recent capture
2. Use spectral_deals_extractor to get deals
3. Output JSON to `~/.let-automation/data/spectral_deals.json`

### 4. Handle Edge Cases

- **No spectral output exists**: Run discovery first, or fallback to BS4
- **Spectral capture is stale** (> 24h old): Warn user, suggest re-running discovery
- **Generated client import fails**: Parse api.yaml directly
- **API endpoints return unexpected format**: Log error, fallback to BS4
- **Rate limiting on discovered API**: Add delays, respect headers

---

## VERIFICATION

### Test 1: Spectral Extractor Works
```bash
cd ~/workspace/let-automation

# Ensure spectral output exists
python spectral-bridge/let_spectral.py discover --no-interactive

# Test extractor
python extractor/spectral_deals_extractor.py --output test_deals.json

# Verify output
cat test_deals.json | jq '.[0] | {title, provider, price_monthly, cpu, ram_gb}'
```

**Expected**: Valid JSON with extracted deals containing specs

### Test 2: Auto Sync Uses Spectral
```bash
# Dry run
python workflows/auto_sync.py --dry-run

# Check logs show "Using spectral extractor"
grep -i "spectral" ~/.let-automation/log/*.md
```

**Expected**: Log shows spectral being used, deals extracted

### Test 3: Excel Generated from Spectral Data
```bash
python workflows/auto_sync.py --no-backup

# Verify Excel
python -c "import pandas as pd; df = pd.read_excel('~/workspace/Hosting-Deals-Tracker.xlsx', sheet_name='Deals Tracker'); print(f'Deals: {len(df)}'); print(df.head())"
```

**Expected**: Excel created with deals from spectral source

### Test 4: Fallback to BS4 Works
```bash
# Temporarily rename spectral output
mv ~/.spectral-nodriver/output ~/.spectral-nodriver/output.bak

# Run sync
python workflows/auto_sync.py --dry-run

# Should show "Falling back to BS4 fetcher"
```

**Expected**: Graceful fallback to RSS/BS4 when spectral unavailable

---

## CONSTRAINTS

1. **Keep BS4 as fallback** - Don't remove existing fetcher, just deprecate primary use
2. **Same output schema** - spectral_deals_extractor must output identical format to let_api_fetcher
3. **No breaking changes** - Existing `let-automation sync` command should still work
4. **Log everything** - Write to log/ which source was used, why fallback occurred
5. **Respect rate limits** - Discovered APIs may have different rate limits than RSS
6. **Thread safety** - Don't break concurrent execution if possible

---

## ACCEPTANCE CRITERIA

- [ ] `extractor/spectral_deals_extractor.py` created and functional
- [ ] `auto_sync.py` modified to try spectral first, fallback to BS4
- [ ] CLI flags `--force-spectral` and `--force-bs4` work
- [ ] Excel output identical regardless of source (spectral vs BS4)
- [ ] All 4 verification tests pass
- [ ] Logs clearly indicate which data source was used
- [ ] AGENTS.md updated with new workflow
- [ ] implementation_plan.md updated (Phase 2 at 100%)

---

## RELATED FILES

### To Read:
- `workspace/let-automation/fetcher/let_api_fetcher.py` - Current fetcher for reference
- `workspace/let-automation/spectral-bridge/let_spectral.py` - Spectral bridge
- `workspace/spectral-nodriver/spectral_nodriver.py` - Spectral integration

### To Create:
- `workspace/let-automation/extractor/__init__.py`
- `workspace/let-automation/extractor/spectral_deals_extractor.py`

### To Modify:
- `workspace/let-automation/workflows/auto_sync.py` - Add spectral step
- `workspace/let-automation/spectral-bridge/let_spectral.py` - Add extract command

---

## NOTES

### Spectral Output Structure:
```
~/.spectral-nodriver/output/
└── lowendtalk_com_20250220_143015/
    ├── api.yaml              # OpenAPI 3.1 spec
    ├── api.graphql           # SDL (if GraphQL)
    ├── api.restish.json      # Restish config
    └── lowendtalk_com_automation.py  # Generated Python client
```

### Key API Endpoints to Map:
- Discussions list → deals list
- Discussion detail → deal content + specs
- Comments → content preview

### Generated Client Usage:
```python
# Generated client pattern
from lowendtalk_com_automation import LowendtalkComClient

client = LowendtalkComClient()
discussions = client.get_discussions()
for d in discussions:
    detail = client.get_discussion(d['id'])
    # Transform to deal schema
```

---

## ESTIMATED EFFORT

- extractor/spectral_deals_extractor.py: 2-3 hours
- auto_sync.py modifications: 1 hour
- Testing & verification: 1 hour
- **Total**: 4-5 hours

---

## DEPENDENCIES

- spectral-nodriver must be installed and working
- At least one spectral discovery run must exist
- let_api_fetcher.py must remain functional (fallback)

---

*Created: 200226-16-35*
*Author: Kimi*
*Priority: HIGH*
