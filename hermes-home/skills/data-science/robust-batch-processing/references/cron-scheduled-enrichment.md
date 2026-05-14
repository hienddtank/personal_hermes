# Cron-Scheduled Enrichment: Korean Professor Email Hunter

## Problem

Enrich 735 professor records with emails from multiple APIs (Semantic Scholar, CrossRef, OpenAlex, university patterns). Must run during user's inactive hours (10pm-7am GMT+7), survive interruptions, resume from checkpoint.

## Solution Architecture

```
┌─────────────┐    ┌──────────────┐    ┌───────────┐
│  Cron 30m    │───▶│  runner.sh   │───▶│ batch_    │
│  (check)     │    │  (start/kill)│    │ hunter.py │
└─────────────┘    └──────────────┘    └───────────┘
                                             │
┌─────────────┐    ┌──────────────┐         ▼
│  Cron 6h    │───▶│ check_       │    CSV (save/row)
│  (report)   │    │ progress.py  │
└─────────────┘    └──────────────┘
```

## Key Files

### runner.sh (timezone-aware)
```bash
CURRENT_UTC_HOUR=$(date -u +%H)
# 10pm GMT+7 = 3pm UTC, 7am GMT+7 = midnight UTC
if [ "$CURRENT_UTC_HOUR" -ge 0 ] && [ "$CURRENT_UTC_HOUR" -lt 15 ]; then
    pkill -f batch_email_hunter 2>/dev/null
    exit 0
fi
pgrep -f batch_email_hunter > /dev/null || {
    cd /path/to/fish_profs && nohup python3 batch_email_hunter.py >> log 2>&1 &
}
```

### batch_email_hunter.py (4 strategies)
1. **Semantic Scholar API** — author profiles (fastest, ~0.5s)
2. **CrossRef API** — corresponding author emails from publications (~1s)
3. **OpenAlex via ORCID** — paper metadata + PDF text extraction (~1s)
4. **University patterns** — generate common Korean email formats, DNS-check domain

### Email Validation Filter
```python
def is_valid_email(email, name):
    local = email.split('@')[0]
    # Skip initials (single char)
    if len(local) < 2: return False
    # Skip publisher domains
    skip_domains = ['springernature.com', 'wiley.com', 'ieee.org', ...]
    if email.split('@')[1] in skip_domains: return False
    # Skip generic addresses
    if local.lower() in ['info', 'admin', 'editor', ...]: return False
    return True
```

## Results

- 735 professors, ~14 emails found in first hour
- Success rate ~2% (most Korean professor emails not in public APIs)
- CSV saves after each row — safe to interrupt/restart
- Auto-pauses at 7am GMT+7, resumes 10pm

## Lessons

1. **API rate limits matter**: Semantic Scholar allows ~1 req/s, CrossRef ~1/15s. Space calls.
2. **Email validation is critical**: Without filtering, you get publisher/editorial emails.
3. **Korean academic sites blocked**: Can't scrape .ac.kr sites from this server (geo-blocked).
4. **CSV checkpointing simpler than JSON**: For tabular data, just save the CSV after each row.
