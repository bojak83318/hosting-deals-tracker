# 🤖 let-automation: LowEndTalk Deals Automation

[![Cloud LET Run](https://github.com/bojak83318/hosting-deals-tracker/actions/workflows/cloud-run.yml/badge.svg)](https://github.com/bojak83318/hosting-deals-tracker/actions/workflows/cloud-run.yml)

> **Deterministic Pipeline: Fetch → Parse → Deduplicate → Excel + GitHub**

A fully automated workflow that replaces manual Power Query with a deterministic, programmatic approach to tracking hosting deals from LowEndTalk.

---

## 🎯 Summary: Deterministic Pipeline Created

### 📁 New Files Created

| File | Purpose |
|------|---------|
| `fetcher/let_api_fetcher.py` | ⭐ **Deterministic fetcher** - Replaces Power Query with programmatic RSS/page fetching + regex spec extraction |
| `excel-sync/deterministic_excel.py` | ⭐ **Auto-Excel generator** - Creates all 5 sheets with color-coding, no formulas needed |
| `workflows/auto_sync.py` | ⭐ **One-command pipeline** - Orchestrates fetch → parse → dedupe → Excel |
| `demo.py` | Visual demo showing old vs new workflow |
| `README.md` | Full documentation with comparisons |

---

## 🆚 Old vs New

### ❌ OLD (Power Query)

```
Manual: Excel → Data → From Web → Enter URL → Select Table → Formula dedupe → Copy-paste Offer Details
Time: 10-15 min | Fragile, inconsistent
```

### ✅ NEW (Deterministic)

```bash
let-automation sync
Time: 30 sec | Reliable, consistent, automated
```

**Automatically creates Excel with:**
- 🟢 **NEW** deals (< 7 days) - Green
- 🔵 **ACTIVE** deals (7-30 days) - Blue
- ⚪ **EXPIRED** deals (> 30 days) - Gray
- 🔴 **DUPLICATES** - Red highlighting
- **Offer Details** sheet with auto-extracted specs

---

## 🚀 Usage

```bash
# Full sync (fetch + Excel)
let-automation sync

# With GitHub backup
let-automation sync --github

# Preview without executing
let-automation sync --dry-run

# Just fetch to JSON
let-automation fetch

# Demo the workflow
python3 ~/workspace/let-automation/demo.py

# Run subagent workflow plan
python3 workflows/workflow_executor.py --workflow workflows/subagents.yaml --dry-run
```

---

## 📚 Documentation

- Deployment guide: [DEPLOYMENT.md](DEPLOYMENT.md)
- Troubleshooting guide: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- Daily cron example: [examples/crontab.txt](examples/crontab.txt)
- Full CI/CD workflow example: [examples/github-actions.yml](examples/github-actions.yml)
- Discord webhook setup: [examples/discord-webhook-setup.md](examples/discord-webhook-setup.md)

---

## ☁️ Cloud Run Button Flow

This repo now supports the cloud chain you described:

`Run button -> GitHub Actions -> llm_router -> spectral -> lowendtalk.com -> excel`

Workflow file:
- `.github/workflows/cloud-run.yml`

Runner script:
- `workflows/cloud_run.py`

Outputs per run:
- `output/Hosting-Deals-Tracker.xlsx`
- `output/cloud_run_report.json`
- GitHub Actions artifact upload for both files

### Run from GitHub UI
1. Open **Actions** tab.
2. Select **Cloud LET Run**.
3. Click **Run workflow**.
4. Set:
   - `command` (natural language routing input)
   - `router_provider` (`rule`, `claude`, or `openai`)
   - `run_spectral` (`true` or `false`)

### Run from API (external "Run button")

```bash
curl -X POST \
  -H "Authorization: Bearer <GH_PAT>" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/<owner>/<repo>/dispatches \
  -d '{
    "event_type": "let_run",
    "client_payload": {
      "command": "Sync latest LowEndTalk deals to excel and github",
      "router_provider": "rule",
      "run_spectral": true
    }
  }'
```

### Required Secrets (optional by provider)
- `CLAUDE_API_KEY` (if using `router_provider=claude`)
- `OPENAI_API_KEY` (if using `router_provider=openai`)

If no LLM API key is set, use `router_provider=rule`.

---

## 🔧 Key Improvements

| Feature | Old Power Query | New Automation |
|---------|-----------------|----------------|
| **Fetching** | Manual UI clicks | `requests` + RSS API |
| **Spec extraction** | Manual copy-paste | Regex patterns auto-extract |
| **Deduplication** | `=COUNTIF()` formula | Deterministic `thread_id+title` |
| **Offer Details** | Manual entry | Auto-populated from parsed specs |
| **Dashboard** | Manual updates | Auto-calculated metrics |
| **Time** | 10-15 min | 30 sec |

---

## 📊 Spec Extraction (Auto)

From deal text like:

```
"RackNerd - 2GB KVM VPS, 2 vCPU, 40GB SSD, 3TB BW - $18.99/year"
```

Automatically extracts:

```json
{
  "provider": "RackNerd",
  "category": "VPS",
  "cpu": 2,
  "ram_gb": 2,
  "storage_gb": 40,
  "storage_type": "SSD",
  "bandwidth": 3000,
  "price_yearly": 18.99
}
```

---

## 🏗️ Architecture

```
┌───────────────────────────────────────────────────────────────────────────┐
│                         DETERMINISTIC PIPELINE                            │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌─────────────────┐                                                      │
│  │  LowEndTalk.com │ ◄── RSS Feed + Discussion Pages (reliable, fast)    │
│  └────────┬────────┘                                                      │
│           │                                                               │
│  ┌────────▼────────┐     ┌─────────────────────────────────────────┐     │
│  │  let_api_fetcher│────▶│  Regex-based spec extraction:           │     │
│  │                 │     │  • vCPU count                           │     │
│  │  • Fetches RSS  │     │  • RAM (GB)                             │     │
│  │  • Fetches pages│     │  • Storage (GB) + type (SSD/NVMe/HDD)   │     │
│  │  • Parses HTML  │     │  • Bandwidth                            │     │
│  └────────┬────────┘     │  • IPv4/IPv6                            │     │
│           │              │  • Monthly/Yearly price                 │     │
│  ┌────────▼────────┐     │  • Location                             │     │
│  │  Deduplication  │     └─────────────────────────────────────────┘     │
│  │                 │                                                       │
│  │  Key: thread_id│                                                       │
│  │       + title   │                                                       │
│  └────────┬────────┘                                                       │
│           │                                                                │
│  ┌────────▼────────┐     ┌─────────────────────────────────────────┐      │
│  │  deterministic_ │────▶│  5 Auto-generated Sheets:               │      │
│  │  excel.py       │     │                                         │      │
│  │                 │     │  1. Deals Tracker (all deals)           │      │
│  │  • DataFrames   │     │     • Color-coded status                │      │
│  │  • Formatting   │     │     • Auto-filters                      │      │
│  │  • Charts       │     │                                         │      │
│  └────────┬────────┘     │  2. Deduplicated View (unique only)     │      │
│           │              │                                         │      │
│           ├─────────────▶│  3. Offer Details (technical specs)     │      │
│           │              │     • Auto-extracted from content       │      │
│           │              │                                         │      │
│           └─────────────▶│  4. Dashboard (metrics & stats)         │      │
│                          │     • Auto-calculated                   │      │
│                          │                                         │      │
│                          │  5. Raw Data (reference)                │      │
│                          └─────────────────────────────────────────┘      │
│                                                                           │
│  Optional:                                                                │
│  ┌─────────────────┐                                                      │
│  │  GitHub Sync    │ ◄── JSON + YAML upload to repo                      │
│  └─────────────────┘                                                      │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Installation

```bash
# Clone and setup
cd ~/workspace/let-automation
pip install pandas openpyxl requests beautifulsoup4

# Make executable
chmod +x let-automation
ln -sf ~/workspace/let-automation/let-automation ~/bin/let-automation
```

---

## 📊 Excel Output (Auto-Generated)

### Sheet 1: Deals Tracker
| Column | Description |
|--------|-------------|
| Thread ID | Unique identifier |
| Thread Title | Deal title |
| Author | LET username |
| Post Date | When posted |
| Provider | Detected company |
| Category | VPS/Dedicated/Shared |
| **Status** | 🟢NEW / 🔵ACTIVE / ⚪EXPIRED |
| **Is Duplicate** | 🔴YES / NO |
| Price (Monthly) | Extracted price |
| vCPU / RAM / Storage | Technical specs |
| Location | Datacenter |
| Source URL | Link to discussion |

### Sheet 2: Deduplicated View
- Same columns as Deals Tracker
- Only unique deals (no duplicates)

### Sheet 3: Offer Details
Pre-populated technical specifications:
- Provider, Category, Post Date, Status
- **vCPU**, **RAM (GB)**, **Storage (GB)**
- **Storage Type** (SSD/NVMe/HDD)
- **Bandwidth (GB)**
- **IPv4/IPv6**
- **Location**
- **Monthly/Yearly Price**

### Sheet 4: Dashboard
Auto-calculated metrics:
- Total / Unique / Duplicate counts
- Deals by Status (NEW/ACTIVE/EXPIRED)
- Deals by Category (VPS/Dedicated/Shared)
- Price statistics (min/max/avg/median)
- Average specs (vCPU, RAM, Storage)
- Top 10 Providers
- Last Updated timestamp

### Sheet 5: Raw Data
- Complete JSON data for reference

---

## 🎨 Color Coding

| Color | Meaning | Trigger |
|-------|---------|---------|
| 🟢 **Green** | NEW deal | < 7 days old |
| 🔵 **Blue** | ACTIVE deal | 7-30 days old |
| ⚪ **Gray** | EXPIRED | > 30 days old |
| 🔴 **Red** | DUPLICATE | Same thread_id+title |

---

## 📋 Usage Examples

```bash
# Daily sync (recommended)
let-automation sync

# Sync with GitHub backup
let-automation sync --github

# Just fetch to JSON (inspect before Excel)
let-automation fetch
cat ~/.let-automation/data/latest.json | jq '.[] | {title, provider, price_monthly}'

# Update Excel from existing data
let-automation excel

# Check stats
let-automation stats

# Preview what would happen (dry run)
let-automation sync --dry-run

# No backup (faster)
let-automation sync --no-backup
```

---

## 🔐 Environment Variables

```bash
# For GitHub sync
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
export GITHUB_REPO="yourname/hosting-deals-data"

# Optional
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## 🧪 Testing

```bash
# Dry run (no changes)
let-automation sync --dry-run

# Fetch only, inspect JSON
let-automation fetch
cat ~/.let-automation/data/latest.json | jq '.[0]'

# Check a specific deal
cat ~/.let-automation/data/latest.json | jq '.[] | select(.provider=="RackNerd")'

# Run demo
python3 demo.py
```

---

## 📝 License

MIT

---

**Pro tip:** Set up a cron job for daily sync:
```bash
# crontab -e
0 9 * * * ~/bin/let-automation sync --github
```

---

The workflow is ready! Run `let-automation sync` to test it out. 🎉
