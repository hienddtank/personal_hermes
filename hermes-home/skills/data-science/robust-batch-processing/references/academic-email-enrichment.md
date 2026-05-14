# Academic Email Enrichment via APIs

Enriching professor/academic CSVs with contact emails using free APIs. Session: 2026-05-05 (Korea materials science professors, 735 rows).

## API Sources (Ranked by Success Rate)

1. **Semantic Scholar** — `https://api.semanticscholar.org/graph/v1/author/search?query={name}&fields=id,name,email,affiliations&limit=5`
   - Returns author emails directly
   - Rate-limited but generous (~100 req/min)
   - Best for well-published authors

2. **CrossRef** — `https://api.crossref.org/works?query.author={name}&mailto=your@contact.com&rows=5`
   - Returns metadata including corresponding author emails
   - Requires mailto header for email reveal
   - Slower than Semantic Scholar

3. **OpenAlex + ORCID** — `https://api.openalex.org/works?filter=authorships.author.orcid:{orcid}&per_page=5`
   - Get works via ORCID, then scrape landing page PDFs for emails
   - Extract emails from Arxiv HTML or publisher pages
   - Rate-limited (~100 credits/day without key)

4. **University Pattern Matching** — Generate common email patterns, DNS-check domain
   - Fastest, no API call needed
   - Works for known university email conventions

## Korean University Email Patterns

```python
domains = {
    "seoul national university": "snu.ac.kr",
    "kaist": "kaist.ac.kr",
    "korea advanced institute": "kaist.ac.kr",
    "korea university": "korea.ac.kr",
    "yonsei university": "yonsei.ac.kr",
    "hanyang university": "hanyang.ac.kr",
    "postech": "postech.ac.kr",
    "pohang university": "postech.ac.kr",
    "sungkyunkwan": "skku.edu",
    "kyungpook national": "knu.ac.kr",
    "kookmin": "kookmin.ac.kr",
    "konkuk": "konkuk.ac.kr",
    "unist": "unist.ac.kr",
    # ... (see full mapping in script)
}

# Common patterns (last = surname, first = given name):
patterns = [
    f"{last}@{domain}",           # kim@snu.ac.kr
    f"{last}{first[0]}@{domain}",  # kims@kaist.ac.kr
    f"{last}{first}@{domain}",     # kimsun@postech.ac.kr
    f"{first}@{domain}",           # sun@snu.ac.kr
]
```

## Email Validation Rules

Filter out false positives:

```python
def is_valid_email(email, name):
    local = email.split('@')[0]
    domain = email.split('@')[1]
    
    # Skip single character local parts (initials)
    if len(local) < 2:
        return False
    
    # Skip publisher/editorial domains
    skip_domains = ['springernature.com', 'wiley.com', 'ieee.org',
                    'elsevier.com', 'acs.org', 'rsc.org', 'nature.com']
    if domain in skip_domains:
        return False
    
    # Skip non-person local parts
    skip_locals = ['copyright', 'editorial', 'support', 'info', 'help',
                   'webmaster', 'admin', 'contact', 'sales', 'permissions']
    if local.lower() in skip_locals:
        return False
    
    # Prefer academic domains
    if '.ac.kr' in domain or '.edu' in domain or '.re.kr' in domain:
        return True
    
    return True
```

## Pitfalls

1. **Google Search blocked** — From the Hermes container, Google search returns errors/CAPTCHA. Use APIs instead.
2. **Name initials** — Names like "V. Naresh" generate bad patterns. Filter: skip parts ending with `.` or length 1.
3. **Publisher emails** — CrossRef/OpenAlex sometimes return `permissions@springernature.com`. Always filter.
4. **DNS check not enough** — A domain resolving doesn't mean the email exists. SMTP verification is more accurate but slower.
5. **Unicode names** — Korean names may contain special characters (‐ vs -). Normalize with `.replace("‐", "").replace("–", "")`.

## Cron Job Setup

Scripts must live at `/hermes-home/scripts/` (relative to cronjob `script:` field).

```bash
# /hermes-home/scripts/runner.sh
#!/bin/bash
CURRENT_UTC_HOUR=$(date -u +%H)

# Kill zone: user is awake (0am-14pm UTC = 7am-7pm GMT+7)
if [ "$CURRENT_UTC_HOUR" -ge 0 ] && [ "$CURRENT_UTC_HOUR" -lt 15 ]; then
    pkill -f batch_email_hunter 2>/dev/null
    echo "Stopped"
    exit 0
fi

# Run zone: user sleeping
pgrep -f batch_email_hunter > /dev/null || {
    cd /path/to/project && nohup python3 batch_email_hunter.py >> log 2>&1 &
    echo "Started (PID: $!)"
}
```

**Two cron jobs:**
1. Runner (every 30m): Starts/kills based on timezone
2. Progress reporter (every 6h): Sends status to user

## Results

For 735 Korean materials science professors:
- **413 emails found (56.2%)** in ~4 hours
- Top sources: University pattern matching (~70%), Semantic Scholar (~20%), CrossRef (~5%), OpenAlex (~5%)
