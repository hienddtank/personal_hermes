---
name: dataset-comparison
description: Compare two tabular datasets where one is the ground truth (manual/correct) and the other is evaluated against it. Measures per-column match rates, classifies differences into categories, determines which source is more complete, and identifies specific mismatches for manual review.
version: 1.0.0
author: Hermes Agent
tags: [csv, comparison, benchmarking, quality-assessment, data-validation]
---

# Dataset Comparison & Quality Benchmarking

## Purpose
Compare two CSV/Excel datasets where one serves as the "correct" or "gold standard" reference. Evaluate the auto/test dataset against it, measure per-column match rates, classify differences, and produce a structured quality report. Common use case: comparing auto-crawled data against manually verified data to assess crawl quality.

## When to Use
- One dataset is known to be correct (manual verification) and the other is being evaluated (auto-crawl, scraping, AI extraction)
- User asks "is auto similar to manual?" or "which is better?"
- Need per-column match rates and a breakdown of difference types
- Both files have the same basic schema but potentially different column counts

## Core Workflow

### Step 1: Read Headers — Handle BOM AND Schema Mismatches
Both files may use `utf-8-sig` (BOM) encoding. The first column often has a BOM character (`\ufeff`) that makes it invisible in display but causes key mismatches.

```python
import csv, re

def load_csv(path):
    """Load CSV with BOM handling and return list of dicts."""
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames

auto_rows, auto_headers = load_csv('/path/to/auto.csv')
manual_rows, manual_headers = load_csv('/path/to/manual.csv')

# Identify shared columns (intersection of header sets)
shared_cols = [h for h in auto_headers if h in manual_headers]
print(f"Auto headers: {auto_headers}")
print(f"Manual headers: {manual_headers}")
print(f"Shared: {shared_cols}")
```

### Step 2: Build Key-Based Lookups
Use a stable key (Name + Company, email, or user-specified columns) to match rows between datasets.

```python
def build_lookup(rows, key_cols=['Name', 'Company'], val_cols=None):
    """Build dict keyed by normalized values from key_cols."""
    lookup = {}
    for r in rows:
        key = tuple((r.get(c, '') or '').strip().lower() for c in key_cols)
        if val_cols is None:
            vals = {c: (r.get(c, '') or '').strip() for c in set(auto_headers) | set(manual_headers)}
        else:
            vals = {c: (r.get(c, '') or '').strip() for c in val_cols}
        lookup[key] = vals
    return lookup

auto_by_key = build_lookup(auto_rows, key_cols=['Name', 'Company'])
manual_by_key = build_lookup(manual_rows, key_cols=['Name', 'Company'])

common_keys = set(auto_by_key) & set(manual_by_key)
auto_only = set(auto_by_key) - set(manual_by_key)
manual_only = set(manual_by_key) - set(auto_by_key)
```

### Step 3: Cell-Level Comparison — Classify Each Difference
For each common row and each shared column, classify the difference into one of four categories:

1. **Match** — values are identical strings
2. **Auto missed** — auto is empty, manual has data (auto failed to capture)
3. **Auto over-claimed** — auto has data, manual is empty (auto found something manual didn't)
4. **Both different** — both have non-empty but different values

```python
total_cells = 0; matching = 0; diff = 0
auto_missed = 0; auto_over = 0; both_diff = 0
diff_details = []

for key in common_keys:
    a = auto_by_key[key]; m = manual_by_key[key]
    for col in shared_cols:
        total_cells += 1
        av = a.get(col, '')
        mv = m.get(col, '')
        if av == mv:
            matching += 1
        else:
            diff += 1
            if av != '' and mv != '':
                both_diff += 1
                if len(diff_details) < 30:
                    diff_details.append((key, col, av[:80], mv[:80]))
            elif av == '':
                auto_missed += 1
            else:
                auto_over += 1

print(f"Total cells: {total_cells}")
print(f"Match rate: {matching/total_cells*100:.1f}%")
print(f"Different: {diff} ({diff/total_cells*100:.1f}%)")
print(f"  Auto missed (manual has, auto empty): {auto_missed}")
print(f"  Auto over-claimed (auto has, manual empty): {auto_over}")
print(f"  Both have different values: {both_diff}")
```

### Step 4: Per-Column Breakdown
Report match rates per column to identify which fields are weak/strong.

```python
from collections import defaultdict
col_matches = defaultdict(int)
col_diffs = defaultdict(int)

for key in common_keys:
    a = auto_by_key[key]; m = manual_by_key[key]
    for col in shared_cols:
        if a.get(col, '') == m.get(col, ''):
            col_matches[col] += 1
        else:
            col_diffs[col] += 1

for col in sorted(shared_cols):
    total = len(common_keys)
    matches = col_matches.get(col, 0)
    print(f"  {col:20s}: {matches}/{total} match ({matches/total*100:.1f}%) | {col_diffs[col]} diffs")
```

### Step 5: Inspect Each Difference Category
Print samples from each category to help the user judge quality.

```python
# Auto missed — what did auto fail to capture?
print("\n=== AUTO MISSED (manual has, auto empty) ===")
count = 0
for key in sorted(common_keys):
    a = auto_by_key[key]; m = manual_by_key[key]
    for col in shared_cols:
        if a.get(col, '') == '' and m.get(col, '') != '':
            print(f"  [{key[0]}] {col}: MANUAL='{m[col][:80]}'")
            count += 1
            if count >= 15: break
    if count >= 15: break

# Auto over-claimed — what did auto find that manual didn't?
print("\n=== AUTO OVER (auto has, manual empty) ===")
count = 0
for key in sorted(common_keys):
    a = auto_by_key[key]; m = manual_by_key[key]
    for col in shared_cols:
        if a.get(col, '') != '' and m.get(col, '') == '':
            print(f"  [{key[0]}] {col}: AUTO='{a[col][:80]}'")
            count += 1
            if count >= 30: break
    if count >= 30: break

# Both different — where do they disagree?
print("\n=== BOTH DIFFERENT ===")
for key, col, av, mv in diff_details:
    print(f"  [{key}] {col}: AUTO='{av[:70]}' | MANUAL='{mv[:70]}'")
```

### Step 6: Produce Quality Verdict
Based on the data, determine which source is better overall. Key signals:
- **Higher recall**: if auto_over >> auto_missed for a field, auto is MORE complete
- **Higher precision**: if both_diff cases are minor format differences (trailing slashes, case), auto is still good
- Both-different where values are substantively different (wrong email, wrong profile) = lower quality
- Structural issues: mismatched rows (auto-only vs manual-only keys) indicate deduplication problems

```python
for col in ['Email', 'LinkedIn']:
    a_missed = sum(1 for k in common_keys if auto_by_key[k].get(col,'') == '' and manual_by_key[k].get(col,'') != '')
    a_over = sum(1 for k in common_keys if auto_by_key[k].get(col,'') != '' and manual_by_key[k].get(col,'') == '')
    print(f"\n{col}: auto found {a_over} that manual missed, missed {a_missed} that manual has")
    net = a_over - a_missed
    if net > 0:
        print(f"  VERDICT: Auto is BETTER for {col} (+{net} more captured)")
    elif net < 0:
        print(f"  VERDICT: Manual is BETTER for {col} (auto missed {-net})")
    else:
        print(f"  VERDICT: Equal coverage for {col}")
```

## Pitfalls & Troubleshooting

### BOM Characters Break Key Matching
The first column in many CSVs has a UTF-8 BOM (`\ufeff`) prefix. Without `utf-8-sig` encoding, the key `'Name'` becomes `'\ufeffName'` and all lookups fail silently. ALWAYS use `encoding='utf-8-sig'`.

### Column Count Mismatches
One file may have more columns than the other (e.g., manual has Status/PIC that auto doesn't). Use column INTERSECTION for comparison, not union. Extra columns in the manual file should be treated as enrichment fields, not comparison targets.

### Different Row Counts Are Normal
Auto and manual rarely produce identical row sets. Auto may have duplicates or miss rows entirely. Always compute: matched keys, auto-only keys, manual-only keys. Report all three counts.

### "Both Different" May Be Minor Format Variations
LinkedIn URLs often differ only by trailing slash (`/profile` vs `/profile/`) or presence of `www.` prefix. Emails may differ in case. Distinguish between FORMAT differences (same data, cosmetic variation) and SUBSTANTIVE differences (wrong email, wrong profile).

### Small Shared-Sample Percentages for Contact Fields
Email and LinkedIn fields are often empty in BOTH datasets. When computing match rates, report both the overall rate AND the per-column breakdown. A 97% overall match can mask a 60% email match rate if most emails are empty in both files.

### No Pandas Available?
If `pandas` is not installed (sandbox environment), use Python's `csv.DictReader` with `encoding='utf-8-sig'`. The entire comparison script above works with stdlib only.

## Linked Resources
- `references/csv-comparison-patterns.md` — Patterns and edge cases from real-world comparisons
