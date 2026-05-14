---
name: tabular-cross-reference
description: Cross-reference two CSV/Excel datasets, match entries by name/company/email, enrich one list with fields from the other, and output matched results. Covers contact matching, deduplication, and dataset enrichment.
version: 1.0.0
author: Hermes Agent
tags: [csv, excel, cross-reference, matching, deduplication, enrichment]
---

# Tabular Cross-Reference & Enrichment

## Purpose
Match entries between two CSV/Excel files with similar or identical column structures. Use cases: find which exhibition contacts exist in a host agency database, enrich a small list with data from a larger master list, deduplicate records across sources.

## When to Use
- Two tabular files share the same schema (or similar) but different scopes (e.g., 140 exhibition contacts vs 2714 host agencies)
- User wants to find overlaps and extract specific fields (IG handles, emails, LinkedIn profiles) from matched records
- Original files must NOT be modified

## Core Workflow

### Step 1: Read Both Files -- Handle Non-Standard Headers AND Schema Mismatches
Business CSVs often have summary rows BEFORE the actual column headers, AND similar-looking files may have DIFFERENT column counts/order. Always:

```python
# Scan for header row dynamically by looking for a distinctive column name
header_idx = None
for i, row in enumerate(all_rows):
    if 'Contact Name' in row:  # Use a distinctive column name from expected schema
        header_idx = i
        break
headers = all_rows[header_idx]

# Parse data rows with padding/slicing for inconsistent column counts
for row in all_rows[header_idx + 1:]:
    if any(cell.strip() for cell in row[:2]):  # Skip empty rows
        padded = list(row)[:len(headers)] + [''] * max(0, len(headers) - len(row))
        records.append(dict(zip(headers, padded)))
```

**CRITICAL: Column Index Mismatch** — Two CSVs that look identical may have DIFFERENT column counts or ordering (e.g., 31 vs 32 cols). NEVER use positional indices like `row[29]` to grab a field. Always map by header name:

```python
# WRONG: assuming both files have Ig at index 29
ig_value = row[29]  

# RIGHT: map headers explicitly, then look up by key
field_map = dict(zip(headers, row))
ig_value = field_map.get('Ig', '')
```

Always compare header lists between files BEFORE matching to identify offset differences. Check `len(headers_a) == len(headers_b)` and list any divergences. This is the #1 cause of "missing" data when columns are shifted or reordered.

**Pitfall:** Never assume header is on row 1, and never assume column positions align between files even if they look like the same dataset.

### Step 2: Build Indexed Lookups
For efficient matching, build dictionaries indexed by normalized name and company:

```python
def normalize_name(name):
    if not name or not name.strip(): return ''
    n = str(name).strip().lower()
    n = re.sub(r'\b(the|of|&|llc|inc|ltd|corp|co|group)\b', '', n)
    n = re.sub(r'[\s_.,\-/]+', ' ', n).strip()
    return n

# Name + Company index for exact matching
name_company_index = {}
for ha in host_agencies:
    key = (normalize_name(ha['Contact Name']), normalize_name(ha.get('Company Name', '')))
    if key not in name_company_index:
        name_company_index[key] = []
    name_company_index[key].append(ha)

# Name-only index as fallback (first + last word)
name_only_index = {}
for ha in host_agencies:
    name = normalize_name(ha['Contact Name'])
    parts = name.split()
    if len(parts) >= 2:
        key = (parts[0], parts[-1])
        if key not in name_only_index:
            name_only_index[key] = []
        name_only_index[key].append(ha)
```

### Step 3: Multi-Strategy Matching
Apply matching strategies in order of strictness:

1. **Name + Company exact match** (highest confidence, score >= 3) -- use the (norm_name, norm_company) index
2. **Name-only with company scoring** -- match on name first via name_only_index, then score how well company aligns (score 1 = name only, score 3 = name + company)
3. **Substring fallback** -- if one normalized name is contained in another (use sparingly)

```python
def names_match(n1, n2):
    n1, n2 = normalize_name(n1), normalize_name(n2)
    if not n1 or not n2: return False
    if n1 == n2: return True
    p1, p2 = n1.split(), n2.split()
    if len(p1) >= 2 and len(p2) >= 2:
        if p1[0] == p2[0] and p1[-1] == p2[-1]: return True
    if len(n1) > 3 and n1 in n2: return True
    return False

def companies_match(c1, c2):
    if not c1 or not c2: return False
    c1, c2 = normalize_name(c1), normalize_name(c2)
    if c1 == c2: return True
    return c1 in c2 or c2 in c1

# Apply strategies in order of strictness
candidates = []
key = (normalize_name(ex_name), normalize_name(ex_company))
if key in name_company_index:
    candidates.append((3, name_company_index[key][0]))  # Score 3 = HIGH

# Name-only fallback with company scoring
parts = normalize_name(ex_name).split()
if len(parts) >= 2 and ex_company:
    for (k_name, k_comp), ha_list in name_only_index.items():
        if k_name == parts[0] and k_comp == parts[-1]:
            for ha in ha_list:
                score = 1  # Base score for name match
                if companies_match(ex_company, get_clean(ha.get('Company Name', ''))):
                    score += 2  # Company also matches -- upgrade to HIGH
                if not any(c[1] is ha for c in candidates):
                    candidates.append((score, ha))

candidates.sort(key=lambda x: x[0], reverse=True)
quality = 'HIGH' if candidates and candidates[0][0] >= 3 else 'MEDIUM' if candidates else None
```

### Step 4: Output Matched Records Only
Write a clean output file with only matched entries. Never modify originals. Report stats.

```python
with open(output_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=out_headers)
    writer.writeheader()
    for r in results:
        if r['_quality']:
            writer.writerow({...})

# Report stats
print(f"Total checked: {N}, Matched: {M}, Not matched: {N-M}")
```

## Field Extraction After Match
Once matched, extract the specific fields the user wants (IG handles, emails, etc.) from the source that has richer data. Report stats on how many have the target field populated vs empty.

## Pitfalls & Troubleshooting

### Summary/Statistics Rows Before Headers
Business CSVs often have 2-3 rows of summary data (Totals, percentages) before the actual header row. Always scan for a distinctive column name instead of assuming row[0] is the header.

### Column Count Inconsistency
Rows may have more or fewer columns than the header. Always apply both padding and slicing:
```python
padded = list(row)[:len(headers)] + [''] * max(0, len(headers) - len(row))
```

### Name Normalization Edge Cases
- Remove common words (the, of, inc, llc, co, group)
- Collapse whitespace/punctuation to single spaces
- Lowercase everything before comparison
- First+last word matching catches partial name matches
- Avoid relying solely on email or LinkedIn for matching -- causes cross-company false positives

### Target Field May Contain Data from Wrong Person
When enriching contact lists, the target field (e.g., Instagram handle) in the source dataset may belong to a colleague at the same company rather than the matched individual. Always flag this and let the user decide whether to verify.

### Name Spelling Variations Break Exact Matches
Common real-world issues: truncated names ("Louise Whitne" vs "Louise Whitney"), nicknames ("Arthur" vs "Art"), title prefixes ("Mrs Alexandra Vega"). These break exact name matching. Mitigations:
- Use first+last word normalization as a fallback index (already covered in Step 2)
- Report unmatched entries with their company names so user can manually verify
- Consider fuzzy string matching (e.g., `difflib.get_close_matches`) only for edge cases after standard strategies fail

### Broken Instagram URL Patterns in Source Data
When the target field is an IG handle, expect these broken patterns and normalize to `https://www.instagram.com/handle`:
- **Query params**: `?igsh=...`, `?hl=en`, `?utm_source=qr` — always strip
- **Profile card redirects**: `/handle/profilecard/?igsh=...` — extract username before `/profilecard/`
- **Content links**: `/reel/xxx`, `/p/xxx`, `/tv/xxx` — extract profile handle from path
- **Non-IG URLs stored as IG**: `https://dorislanghouseoftravel.net` or `https://Www.ourwholevillage.com` — strip TLD and use as handle
- Use the provided script: `scripts/ig-url-normalizer.py` to bulk-fix

### Docker 9p Mount File Permissions Block Linux rm
When working with files on a Windows drive mounted via Docker 9p (`/host/d/...`), files created by Windows may have execute permission bits set. These persist even after `chmod` from Linux and block `rm` with "Permission denied." Mitigation:
- Use PowerShell or cmd.exe from the host to delete problematic files
- Or access the file via a writable mount point (e.g., workspace dir) if possible
- Report this limitation to the user and offer manual deletion on Windows

## Linked Resources
- `scripts/ig-url-normalizer.py` -- Fixes broken Instagram URLs to proper https://www.instagram.com/... format (handles missing domain, @ prefix, stray TLDs)

## Related
For travel-industry-specific cross-reference patterns (false positive avoidance on generic company names):
→ See `tabular-data` skill, `references/travel-company-cross-reference.md`