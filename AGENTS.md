# 🤖 AGENTS.md - AI Agent Instructions

> Protocol for AI assistants working on the let-automation project

---

## 📋 Required Files Structure

When working on this project, maintain these 4 files:

```
let-automation/
├── AGENTS.md              # This file - instructions & protocols
├── implementation_plan.md # Current implementation roadmap
├── task.md               # Active tasks & backlog
└── log/                  # Timestamped logs DDMMYY-HH-MM-SS.md
    ├── 200224-14-32-15.md
    ├── 200224-15-10-22.md
    └── ...
```

---

## 🔄 Agent Workflow Protocol

### Data Pipeline Default (Updated 20-02-2026)

Primary extraction path is now:
`router -> spectral-nodriver -> spectral analyze -> extractor/spectral_deals_extractor.py -> workflows/auto_sync.py -> excel`

Fallback path remains available:
`router -> fetcher/let_api_fetcher.py (RSS/BS4) -> workflows/auto_sync.py -> excel`

When touching fetch orchestration:
- Keep BS4 path working as fallback
- Log selected source (`spectral` vs `bs4`) and fallback reason
- Preserve deal schema compatibility for Excel sheets

### BEFORE Starting Work:

1. **Read Current State**
   ```bash
   # Check what was last done
   cat task.md
   ls -la log/ | tail -5
   cat log/$(ls -t log/ | head -1)  # Last log entry
   ```

2. **Update Task.md**
   - Move task from `## Backlog` to `## In Progress`
   - Add your name/timestamp

### DURING Work:

3. **Log Everything**
   - Create timestamped log entry for EVERY significant action
   - Include: commands run, outputs, errors, decisions

### AFTER Work:

4. **Update Task.md**
   - Move completed tasks to `## Completed`
   - Add new discovered tasks to `## Backlog`

5. **Update Implementation_Plan.md**
   - Mark completed milestones
   - Add new discoveries
   - Update progress percentages

6. **Update AGENTS.md (if protocols change)**

---

## 📝 Log File Format

### Filename Convention:
```
DDMMYY-HH-MM-SS.md

Examples:
- 200224-14-32-15.md  (Feb 20, 2024, 14:32:15)
- 200224-15-10-22.md  (Feb 20, 2024, 15:10:22)
```

### Log Entry Template:

```markdown
# Log Entry: DDMMYY-HH-MM-SS

## Session Info
- **Date**: 20 Feb 2024
- **Time Started**: 14:32:15
- **Agent**: Kimi/Claude/GPT
- **Task**: Brief description

## Actions Performed

### 1. [Action Name]
**Command/Action**:
```bash
command here
```

**Output**:
```
output here
```

**Result**: ✅ Success / ❌ Failed / ⚠️ Partial

### 2. [Next Action]
...

## Files Modified
- `path/to/file.py` - Description of change
- `path/to/file2.py` - Description of change

## Decisions Made
- Decision 1: Why X instead of Y
- Decision 2: Trade-offs considered

## Errors Encountered
- **Error**: Description
- **Solution**: How it was fixed / Workaround

## Next Steps
1. [ ] Next action needed
2. [ ] Another pending item

## Artifacts Created
- `/path/to/output.json`
- `/path/to/report.xlsx`
```

---

## 📊 Task.md Format

```markdown
# Task Board - let-automation

## Legend
- 🔴 BLOCKED - Cannot proceed, needs external input
- 🟡 IN PROGRESS - Currently being worked on
- 🟢 READY - Can be started
- ⚪ BACKLOG - Future ideas

---

## 🔴 Blocked

### BLOCK-001: GitHub API Rate Limiting
- **Issue**: Hit rate limit during testing
- **Blocked Since**: 20-02-24 15:00
- **Resolution**: Wait 1 hour OR use different token
- **Assigned**: -

---

## 🟡 In Progress

### TASK-001: Create Deterministic Fetcher
- **Description**: Build let_api_fetcher.py to replace Power Query
- **Started**: 20-02-24 14:30
- **Agent**: Kimi
- **Status**: 80% complete
- **Files**: `fetcher/let_api_fetcher.py`

#### Checklist:
- [x] RSS feed fetching
- [x] Page scraping
- [x] Spec extraction
- [ ] Error handling
- [ ] Unit tests

---

## 🟢 Ready (Next Up)

### TASK-002: Excel Integration
- **Priority**: High
- **Description**: Connect fetcher to Excel output
- **Depends On**: TASK-001
- **Estimated**: 2 hours

### TASK-003: GitHub Sync
- **Priority**: Medium
- **Description**: Upload deals to GitHub repo
- **Depends On**: TASK-002
- **Estimated**: 1 hour

---

## ⚪ Backlog

### IDEA-001: Web Dashboard
- **Description**: Web UI for viewing deals
- **Priority**: Low
- **Notes**: Nice to have, not critical

### IDEA-002: Price History Tracking
- **Description**: Track price changes over time
- **Priority**: Medium
- **Notes**: Would need database

---

## ✅ Completed (Last 10)

### TASK-000: Project Setup
- **Completed**: 20-02-24 14:00
- **Agent**: Kimi
- **Summary**: Created directory structure, README
```

---

## 📋 Implementation_Plan.md Format

```markdown
# Implementation Plan - let-automation

> Living document tracking overall project progress

---

## 🎯 Project Goal

Fully automated LowEndTalk deals tracking pipeline that:
1. Fetches deals programmatically (no Power Query)
2. Extracts structured specs automatically
3. Deduplicates deterministically
4. Generates formatted Excel
5. Syncs to GitHub (optional)

---

## 📊 Overall Progress: 75%

```
Phase 1: Core Infrastructure    [████████░░] 80%
Phase 2: Data Pipeline           [████████░░] 90%
Phase 3: Excel Integration       [██████░░░░] 60%
Phase 4: GitHub Integration      [████░░░░░░] 40%
Phase 5: Polish & Tests          [██░░░░░░░░] 20%
```

---

## 🏗️ Phase 1: Core Infrastructure (80%)

### Milestones:

#### M1.1: Project Structure ✅
- [x] Directory layout
- [x] README.md
- [x] AGENTS.md
- [x] CLI entry point

#### M1.2: Dependencies ✅
- [x] requirements.txt
- [x] Setup instructions
- [x] Dependency checking

#### M1.3: Configuration System 🟡
- [x] Environment variables
- [x] Config file support
- [ ] Config validation

---

## 🏗️ Phase 2: Data Pipeline (90%)

### Milestones:

#### M2.1: Fetcher Module ✅
- [x] RSS feed parsing
- [x] Page scraping
- [x] Retry logic
- [ ] Rate limiting

#### M2.2: Spec Extraction ✅
- [x] Regex patterns for specs
- [x] Provider detection
- [x] Category classification
- [ ] Price normalization

#### M2.3: Deduplication ✅
- [x] Deterministic dedup logic
- [x] Thread ID tracking
- [x] Title normalization

---

## 🏗️ Phase 3: Excel Integration (60%)

### Milestones:

#### M3.1: Excel Writer 🟡
- [x] Basic sheet generation
- [x] Formatting
- [x] Color coding
- [ ] Charts

#### M3.2: Sheet Templates ✅
- [x] Deals Tracker
- [x] Deduplicated View
- [x] Offer Details
- [x] Dashboard

#### M3.3: Data Updates 🟡
- [x] Append new deals
- [ ] Update existing
- [ ] Backup/restore

---

## 🏗️ Phase 4: GitHub Integration (40%)

### Milestones:

#### M4.1: GitHub API 🟡
- [x] Token auth
- [x] Repo creation
- [ ] File upload

#### M4.2: Sync Logic 🔴
- [ ] JSON upload
- [ ] YAML upload
- [ ] PR creation

---

## 🏗️ Phase 5: Polish & Tests (20%)

### Milestones:

#### M5.1: Testing 🔴
- [ ] Unit tests
- [ ] Integration tests
- [ ] Mock data

#### M5.2: Documentation ✅
- [x] README
- [x] Code comments
- [ ] API docs

#### M5.3: Error Handling 🟡
- [x] Basic error handling
- [ ] Retry with backoff
- [ ] User-friendly messages

---

## 🚀 Current Sprint: Excel Polish

**Sprint Goal**: Get Excel output production-ready

**Start**: 20-02-24
**End**: 21-02-24

### Sprint Tasks:
1. [x] Fix column widths
2. [x] Add filters
3. [ ] Add charts to Dashboard
4. [ ] Test with real data
5. [ ] Backup before overwrite

---

## 📅 Timeline

| Phase | Start | End | Status |
|-------|-------|-----|--------|
| Phase 1 | 20-02 | 20-02 | ✅ Done |
| Phase 2 | 20-02 | 20-02 | ✅ Done |
| Phase 3 | 20-02 | 21-02 | 🟡 Active |
| Phase 4 | 21-02 | 22-02 | ⏳ Planned |
| Phase 5 | 22-02 | 23-02 | ⏳ Planned |

---

## 🐛 Known Issues

1. **ISSUE-001**: Excel backup not working on Windows
   - **Workaround**: Manual backup
   - **Fix Priority**: Medium

2. **ISSUE-002**: Rate limiting on LET during testing
   - **Workaround**: Add delays
   - **Fix Priority**: High

---

## 💡 Future Enhancements

- [ ] SQLite database for history
- [ ] Web dashboard
- [ ] Email alerts for hot deals
- [ ] Discord integration
- [ ] Price tracking over time
```

---

## 🎯 Quick Commands for Agents

### Create New Log Entry:
```bash
LOGDIR="/home/rocm/workspace/let-automation/log"
mkdir -p "$LOGDIR"
TIMESTAMP=$(date +"%d%m%y-%H-%M-%S")
LOGFILE="$LOGDIR/$TIMESTAMP.md"

cat > "$LOGFILE" << 'EOF'
# Log Entry: TIMESTAMP

## Session Info
- **Date**: $(date +"%d %b %Y")
- **Time Started**: $(date +"%H:%M:%S")
- **Agent**: [Name]
- **Task**: [Brief description]

## Actions Performed

### 1. [Action Name]
**Command**:
\`\`\`bash
# command here
\`\`\`

**Output**:
\`\`\`
# output here
\`\`\`

**Result**: ✅ / ❌ / ⚠️

## Files Modified
- 

## Next Steps
- [ ] 

EOF

echo "Created log: $LOGFILE"
```

### Update Task Status:
```bash
# In task.md, move task between sections
# Update timestamp and progress
```

### Update Implementation Plan:
```bash
# Update progress bars
# Mark milestones complete
# Add new discoveries
```

---

## ⚠️ Critical Rules

1. **ALWAYS log before making changes**
2. **NEVER delete old logs** - archive instead
3. **ALWAYS update task.md after work**
4. **NEVER leave tasks in "In Progress" overnight**
5. **ALWAYS commit significant changes**

---

## 🔍 Self-Correction Protocol

If you make a mistake:

1. **Log it immediately** in current log file
2. **Revert if possible** using git or backups
3. **Document the fix** for future agents
4. **Update task.md** to reflect reality
5. **Adjust implementation_plan.md** if timeline affected

---

## 📝 Example: Complete Workflow

```bash
# 1. Check current state
cat /home/rocm/workspace/let-automation/task.md
cat /home/rocm/workspace/let-automation/log/$(ls -t /home/rocm/workspace/let-automation/log/ | head -1)

# 2. Create log entry for this session
LOGDIR="/home/rocm/workspace/let-automation/log"
mkdir -p "$LOGDIR"
TIMESTAMP=$(date +"%d%m%y-%H-%M-%S")
LOGFILE="$LOGDIR/$TIMESTAMP.md"

# 3. Do the work, logging as you go
echo "### Action 1: Fixed bug" >> "$LOGFILE"

# 4. Update task.md
# Move TASK-001 to Completed

# 5. Update implementation_plan.md  
# Mark M3.1 as complete

# Done!
```

---

**Remember**: The goal is continuity. Any agent should be able to pick up where the last one left off by reading these 4 files.
