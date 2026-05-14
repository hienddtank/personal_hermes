---
name: web-scraping
description: Build Playwright-based crawlers for JS-rendered sites — authentication, session persistence, rate limiting, anti-bot evasion, and structured data extraction.
tags: [playwright, scraping, crawling, browser-automation, data-extraction]
---

# Web Scraping with Playwright

Build automated crawlers using Playwright for JavaScript-rendered websites that require login sessions, have rate limits, or employ anti-bot detection.

## When to Use

- The target site requires **login/authentication** (LinkedIn, Indeed, internal tools)
- Pages are **JS-rendered** and need a real browser
- You're extracting data from **lists of known entities** (names + companies)
- The crawl may take **hours** and needs checkpoint/recovery support

## Not for: Simple HTTP sites → use `http_get` or requests library instead. Sites with strict ToS blocking scraping — assess legal risk first.

---

## Core Architecture

All crawlers follow this pattern:

### 1. Persistent Browser Context
Use `launch_persistent_context()` with a user_data_dir to persist login state across runs:

```python
from playwright.async_api import async_playwright

async def launch():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch_persistent_context(
        user_data_dir="./browser_session",  # persists cookies, localStorage
        headless=False,                     # True for batch runs after login
        viewport={"width": 1280, "height": 900},
        locale="en-US",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    )
    return pw, browser
```

**Critical:** First run MUST use `headless=False` for interactive login. Subsequent runs can use `headless=True`.

### 2. Authentication Flow
Two modes:
- **Auto-detect session**: Navigate to a logged-in page; if URL is not login/checkpoint, skip auth
- **Force login**: Navigate to `/login`, wait for user to complete MFA, verify navigation to `/feed` or similar

```python
async def ensure_logged_in(page):
    # Try loading a protected page
    try:
        await page.goto("https://target.com/feed/", timeout=10000)
        if "login" not in page.url.lower():
            return  # Already logged in
    except:
        pass
    
    # Not logged in — force interactive login
    await page.goto("https://target.com/login")
    while True:
        await asyncio.sleep(1)
        if "/feed" in page.url or "/home" in page.url:
            break  # Login complete
```

### 3. Checkpoint System (Resume on Crash)
Save progress after every record so interruption is safe:

```python
# Save checkpoint atomically (write to .tmp, then rename)
def save_checkpoint(state):
    tmp = CHECKPOINT_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, CHECKPOINT_FILE)

# Resume logic
state = load_checkpoint()
processed_ids = set(state.get("processed", []))
queue = [(i, person) for i, person in enumerate(data) if str(i) not in processed_ids]
```

### 4. Rate Limiting (Anti-Detection)
Always use **randomized delays** between requests:

```python
import random

# Config
MIN_DELAY = 4.0    # seconds — never go below this
MAX_DELAY = 9.0    # seconds — vary the upper bound

delay = random.uniform(MIN_DELAY, MAX_DELAY)
await asyncio.sleep(delay)
```

**Why random:** Fixed intervals are trivially detected by rate limiters. Random delays (4-9s) appear human-like.

### 5. Data Extraction via JS Evaluation
Use `page.evaluate()` to extract structured data from the DOM:

```python
result = await page.evaluate("""() => {
    const cards = document.querySelectorAll('.search-result-card');
    if (!cards.length) return null;
    
    // Extract from first card
    const link = cards[0].querySelector('a[href*="/profile/"]');
    const nameEl = cards[0].querySelector('.name');
    const titleEl = cards[0].querySelector('.title');
    
    return {
        url: link?.href,
        name: nameEl?.innerText.trim(),
        title: titleEl?.innerText.trim()
    };
}""")
```

### 6. Error Handling & Status Tracking
Track outcomes per record:
- `found` — profile scraped successfully
- `no_results` — search returned no matches
- `captcha_blocked` — hit CAPTCHA wall (reduce rate, add human-like behavior)
- `error_navigate` — page load failed (network issue)
- `error_extract` — selectors didn't match

---

## Anti-Bot Evasion Techniques

### Basic (works for most sites)
1. **Persistent context** — preserves cookies and session state
2. **Realistic user agent** — use a current Chrome UA string
3. **Randomized delays** — never fixed intervals
4. **Viewport size** — use common desktop resolution (1280×900 or 1920×1080)

### Advanced (for aggressive sites like LinkedIn, Indeed)
1. **Human-like mouse movement** — add random scroll pauses
2. **Page dwell time** — wait 3-5 seconds before clicking results
3. **Avoid headless fingerprints** — use `headless=False` for the first login window
4. **Session reuse** — persist browser state across runs (not per-run fresh context)
5. **Rate cap** — 15-20 requests before a longer pause (30-60 seconds)

### CAPTCHA Handling
When a CAPTCHA hits:
1. Stop crawling immediately
2. Wait 15-30 minutes
3. Re-login manually with `--force-login`
4. Resume from checkpoint (uses saved progress)

---

## Output Pattern

Always write to CSV incrementally (after each record), not at the end:

```python
def write_output(row, filepath):
    file_exists = filepath.exists() and filepath.stat().st_size > 0
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
```

This way: **zero data loss** even if the process crashes at any point.

---

## Quick Start Checklist

1. [ ] Install: `pip install playwright && playwright install chromium`
2. [ ] Build crawler with persistent context + checkpointing
3. [ ] Run once with `--first-run --headless=False` for interactive login
4. [ ] Verify session saved (check `.linkedin_session/` or equivalent)
5. [ ] Run batch mode: `--headless=True` — resumes from checkpoint
6. [ ] Monitor progress, watch for captcha/block patterns
7. [ ] If blocked: wait 15-30 min → `--force-login` → resume

---

## SPA API Discovery (When the site is a React/Vue/Angular SPA)

**Before investing in full Playwright crawling, check if the SPA has an undocumented API you can call directly.** This is dramatically faster — no browser needed for the actual data extraction.

### Detection
- Page has `<div id="root">` with `<noscript>You need to enable JavaScript</noscript>`
- HTTP response is small HTML shell (20-40KB) with no actual content
- Page title/meta tags are generic, not page-specific

### Discovery Steps

1. **Find the JS bundle**: Look for script tags like `<script src="/assets/index-*.js">`
2. **Download the bundle**: `http_get()` or `requests.get()` with browser User-Agent
3. **Search for API patterns** in the bundle:
   - `fetch(` or `axios(` calls with URL strings
   - Function names like `getAgents`, `searchAdvisors`, `fetchData`
   - URL patterns: `/api/`, `/graphql`, domain-specific paths
4. **Find the API base URL**: Look for `const base = "..."` or `const po = "..."` near the fetch calls. An empty string `""` means the API is at the root of the same domain.
5. **Call the API directly**: Use `requests` with headers including `Referer` and `Origin` set to the site domain.

### Common Patterns Found in SPAs
- Pagination: `CurrentPage=0&PageSize=20` (0-indexed, often accepts large page sizes up to 10,000)
- Total count: response includes `totalAgents`, `totalRows`, `totalPages`
- Filters: URL-encoded query params (`AgentState=CA`, `AgentInterest=Luxury`)

**⚠️ Pitfall**: Some SPAs set the API base URL to empty string `""` meaning same-origin. The actual API is `https://domain.com/agent/getAgents?...` not a separate `/api/` subdomain.

**⚠️ Pitfall**: Large `PageSize` values may be rejected by the server. Test incrementally (100, 500, 1000, 5000, 10000). If 30000 returns empty, fall back to multiple pages of 10,000.

**⚠️ Pitfall — Social links in list response**: Many SPAs include social URLs (`connect[]` or similar) directly in the list endpoint's per-item data — LinkedIn, Instagram, Facebook, Blog, etc. Check `connect[].contactMethod` / `connect[].contactValue` **before** writing individual detail calls. In the TravelLeaders case, `connect[]` had 100% of social URLs, so only bioText required per-agent calls. Always extract from list first before paying the O(N) cost of detail endpoint calls.

- See `references/spa-api-discovery.md` for the TravelLeaders.com case study (23,582 agents via 3 API calls).
- See `references/spa-api-enrichment.md` for post-crawl field completion: enriching an existing CSV with bio text, certifications. **Note**: social URLs (LinkedIn/Instagram/Facebook) are already in the list response's `connect[]` — no detail call needed for those.

---

## Batch Contact Enrichment via Search

When you have a contact list (CSV/Excel with names, companies, emails) and need to discover external platform URLs (LinkedIn profiles, social handles, websites), use targeted web searches instead of full browser automation.

### Core Workflow

1. **Profile the source data** — inspect CSV structure, check what's already filled
2. **Build search queries per record** — use name + company variants with `site:` operators
3. **Execute searches and extract URLs** — use web_search, filter for target domain patterns
4. **Checkpoint and resume** — for lists >100 records, always checkpoint progress
5. **Output enriched CSV** — new file with original + discovered fields

### Query Patterns

| Platform | Query Template |
|---|---|
| LinkedIn | `"FirstName LastName" site:linkedin.com/in/` |
| LinkedIn + Company | `"FirstName LastName" "CompanyName" linkedin` |
| Twitter/X | `"FirstName LastName" site:x.com` |
| GitHub | `"FirstName LastName" site:github.com` |
| Company Site | `"CompanyName" industry-keyword` |

### URL Extraction

```python
import re

def extract_linkedin_url(search_results):
    """Given search results [{title, href, ...}], return best LinkedIn profile URL."""
    linkedin_pattern = r'https?://www\.linkedin\.com/in/[a-zA-Z0-9_-]+'
    for r in search_results:
        url = r.get('href', '') or ''
        if 'linkedin.com/in/' in url.lower():
            match = re.search(linkedin_pattern, url, re.IGNORECASE)
            if match:
                return match.group(0)
    return None  # Report NO_RESULT, don't guess
```

**Pitfall:** Search results may include company pages (`linkedin.com/company/`), group pages, or job postings. Filter to only `/in/` profile URLs.

### Checkpointing for Large Lists

For 10,000+ records × 2 queries each = ~20,000 searches. This is **not** a live task — use background batch with checkpoints:

```python
import json

CHECKPOINT_FILE = "/path/to/output.csv.checkpoint"

def save_checkpoint(start_idx):
    with open(CHECKPOINT_FILE, 'w') as f:
        f.write(str(start_idx))

def load_checkpoint():
    try:
        with open(CHECKPOINT_FILE, 'r') as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0

# Usage:
start_row = load_checkpoint()
for i, row in enumerate(data[start_row:], start=start_row):
    # ... process ...
    if i % 50 == 0:
        save_checkpoint(i)
```

### Rate Limiting

Add delays between searches (1-2 seconds minimum). DuckDuckGo may throttle after rapid requests.

### Common Name Handling

"John Smith" returns thousands of results. Mitigations:
- Always use company as second query variant
- Use full name with middle initial/initials if available
- Try email domain as additional filter: `"FirstName LastName" "company.com"`

### Validation

After enrichment completes:
1. Count filled URLs vs total records
2. Spot-check 5-10 extracted URLs for correctness
3. Ensure no duplicates were introduced
4. Verify original data columns are untouched

---

## Related Resources

- See `references/linkedin-crawling.md` for LinkedIn-specific selectors and pitfalls
- See `references/spa-api-discovery.md` for JS bundle API discovery case study
- See `references/academic-email-finding.md` for academic contact research lessons
- Template at `templates/spa-bulk-crawler.py` — reusable SPA bulk crawler with list API + optional per-record enrichment, social link extraction from connect[], and checkpoint/resume support.
- Template at `templates/crawler-template.py` — scaffold a new Playwright-based crawler.
- Scripts in `scripts/` — verification and utility scripts
