---
name: web-enrichment
description: Batch-discover and enrich contact records (names, companies, emails) with external platform URLs via targeted web searches. Covers LinkedIn discovery, social media handle lookup, and company info enrichment from CSV/Excel lists.
version: 1.0.0
tags: [enrichment, web-search, csv, contacts, scraping, batch-processing]
---

# Web Enrichment — Batch Contact Discovery via Search

## Purpose
Take a contact list (CSV/Excel with names, companies, emails) and discover external platform URLs (LinkedIn profiles, social handles, websites) by running targeted web searches for each person/entity. Output: enriched CSV with original data + discovered URLs.

## When to Use
- You have a list of people (names + emails ± companies) and want their LinkedIn profiles
- Need to enrich contacts with social media handles or company info
- User has thousands of records — must be resumable, checkpointed, not done live

## Core Workflow

### Step 1: Profile the Source Data
Before writing any search logic, inspect the CSV structure:
- Column names for first name, last name, full name, company, email
- Row count (determines if this should run as a background batch)
- Check if the target field (e.g., LinkedIn) already exists — are some filled and others empty?

```python
import csv
with open(file, 'r', encoding='utf-8') as f:
    rows = list(csv.reader(f))
header = rows[0]
print(f"Rows: {len(rows)-1}, Columns: {header[:8]}")  # show first 8 cols
# Check how many already have the target field filled
target_idx = next((i for i,h in enumerate(header) if 'linkedin' in h.lower()), None)
if target_idx:
    filled = sum(1 for r in rows[1:] if r[target_idx].strip())
    print(f"Already have LinkedIn: {filled}/{len(rows)-1}")
```

**Pitfall:** CSV headers may be on a non-first row (summary/statistics rows above). Scan for a distinctive column name instead of assuming `row[0]`.

### Step 2: Build Search Queries Per Record
For each contact, generate search queries using available fields. Always use **both** variants:

| Available Fields | Query 1 (basic) | Query 2 (with company) |
|---|---|---|
| Name only | `"FirstName LastName" site:linkedin.com/in/` | N/A |
| Name + Company | `"FirstName LastName" site:linkedin.com/in/` | `"FirstName LastName" "CompanyName" linkedin` |
| Name + Email | Same as above + try email patterns | N/A |

**Query construction rules:**
- Wrap name in double quotes for exact match
- Use `site:linkedin.com/in/` to narrow to profile URLs
- If company is available, add it as a second query variant
- For difficult-to-find people (common names), email can help disambiguate: `"FirstName LastName" "company.com"` then filter for LinkedIn results

### Step 3: Execute Searches and Extract URLs
Run each query via web search. From results, extract the first plausible LinkedIn URL:

```python
import re

def extract_linkedin_url(search_results):
    """Given a list of {title, href, body} from web search, return best LinkedIn URL."""
    linkedin_pattern = r'https?://www\.linkedin\.com/in/[a-zA-Z0-9_-]+'
    for r in search_results:
        url = r.get('href', '') or ''
        if 'linkedin.com/in/' in url.lower():
            # Validate it looks like a profile (has path segments)
            match = re.search(linkedin_pattern, url, re.IGNORECASE)
            if match:
                return match.group(0)
    return None
```

**Pitfall:** Search results may include company pages (`linkedin.com/company/`), group pages, or job postings. Filter to only `/in/` profile URLs.

### Step 4: Checkpoint and Resume
For lists >100 records, **always** checkpoint progress:

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

**Rate limiting:** Add delays between searches (1-2 seconds minimum). DuckDuckGo may throttle after rapid requests.

### Step 5: Output Enriched CSV
Write a new file with original columns + enriched fields. Never modify originals.

```python
out_headers = original_headers + ['linkedin_url', 'search_status']
with open(output_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=out_headers)
    writer.writeheader()
    for r in enriched_records:
        writer.writerow(r)
```

## Query Patterns for Other Platforms

### Twitter/X
`"FirstName LastName" site:x.com` or `site:twitter.com`

### GitHub
`"FirstName LastName" site:github.com`

### Company Website Discovery
`"CompanyName" travel agency` (industry-specific suffix helps reduce noise)

### Email-Based LinkedIn Lookup
When name is ambiguous but email domain is known: `"FirstName LastName" "company.com"` — then check if any result is a LinkedIn profile.

## Pitfalls & Troubleshooting

### Common Names Return Irrelevant Results
"John Smith" will return thousands of results. Mitigations:
- Always use company as a second query variant
- Use full name with middle initial/initials if available
- Try email domain as additional filter in query

### LinkedIn Blocks Scraped Queries
If search returns no LinkedIn URLs, the person may not have a public profile, or Google hasn't indexed it. Report `NO_RESULT` status rather than guessing.

### Name Normalization Issues
CSV names may be inconsistent: "J. Smith" vs "John Smith", all caps, title prefixes ("Dr", "Mrs"). For search queries, use the full name as-is — Google handles variations well. Don't over-normalize.

### Large Lists Take Hours/Days
14,000 records × 2 searches = ~28,000 API calls. This is **not** a live task. Set it up as a background batch process with checkpoints so it survives timeouts and can resume.

### 9p Mount Permission Issues on /host/d/
Files created by Windows may have execute permission bits that block `rm` from Linux. Use PowerShell or cmd.exe on host to delete, or work in the workspace directory instead.

## Validation
After enrichment completes, verify:
1. Count of filled LinkedIn URLs vs total records
2. Spot-check 5-10 extracted URLs for correctness (not company pages)
3. Check that no duplicates were introduced
4. Ensure original data columns are untouched

## Linked Resources
- `references/user-b2b-data-structure.md` — User's B2B contact data layout (primary file, column names, row counts for Hien's travel agency contact lists)

## Related Skills
- `duckduckgo-search` — the search tool used in this workflow
- `tabular-cross-reference` — when you need to enrich from one dataset using another (instead of web search)
