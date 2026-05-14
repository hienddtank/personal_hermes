---
name: weekly-session-review
description: Weekly Sunday 6AM cron job pattern — scan sessions, update tracker with age/status, then create summaries of review batches.
tags: [cron, sessions, archive]
---

# Weekly Session Review & Revision

Runs every Sunday at 6AM to maintain session hygiene: update the session tracker and generate summaries for review-flagged sessions.

## When to Use
- As a cron job (weekly)
- On-demand maintenance when session count grows large
- After bulk session imports or migrations

## Steps

### 1. Update Tracker
Run the tracker script to scan all session files and classify them:
```python
# Key rules applied during classification:
# - Normal sessions >30 days old → "discard"
# - Cron sessions >14 days old → "archive"
# - Normal sessions >7 days old → "review" (needs summary)
# - Otherwise → "keep"
```

**File locations:**
- Sessions dir: `/host/d/mkt/python/hermes/hermes-home/sessions`
- Tracker: `/root/.hermes/sessions/tracker.json`
- Script: embedded Python in cron prompt (watch for typos like `isron` → `is_cron`)

### 2. Run Session Summarizer
```bash
python3 /root/.hermes/scripts/session_revise.py
```

This processes ~20 "review" sessions per run, creating markdown summaries in the archive directory. Supports cursor-based resumption via `_cursor.json` — if interrupted, it picks up where it left off.

### 3. Report Results
Report:
- Tracker counts (keep/review/discarded)
- Summaries created this run
- Total accumulated summaries in archive/
- Remaining review backlog estimate

## Gotchas
- **Cron script typos:** The provided script often has bugs (e.g., `isron` instead of `is_cron`). Always check before running.
- **Script path:** `/root/.hermes/scripts/session_revise.py` — NOT `/hermes-home/scripts/session_revise.py`.
- **Parallel execution:** Don't run the summarizer in parallel with other tasks — it can cause duplicate cursor state and re-process files.
- **Large backlog:** With ~20 sessions/run and potentially 700+ review sessions, clearing backlog takes ~35 runs. Monitor progress via summary file count in archive/.
- **Tracker not found:** The summarizer requires the tracker to exist first. Always run tracker update before summarizer.

## Verification
After each run:
1. Check `ls ~/.hermes/hermes-home/sessions/archive/summaries/*.summary.md | wc -l` for total summaries
2. Check cursor: `cat ~/.hermes/hermes-home/sessions/archive/summaries/_cursor.json`
3. Verify tracker summary counts changed appropriately
