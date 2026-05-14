# CSV Comparison Patterns — Real-World Cases

## Case: Signature Network Auto vs Manual Crawl (2026-05-04)

### Context
Comparing auto-crawled agent data from Signature Travel Network against manually verified crawl. Files on Windows D: drive (`/host/d/mkt/python/B2B/Signature/`).

### Key Findings
- **Overall match**: 97.1% (1985 matched rows × 12 shared columns = 23,820 cells)
- **Row overlap**: 1985 common keys, auto-only: 25, manual-only: 18
- **Core fields** (Name, Company, Location, Phone, Language): 99.9–100% match
- **Email**: auto found 329 that manual missed vs 64 manual had that auto missed → auto is MORE complete for email
- **LinkedIn**: auto found 169 that manual missed vs 89 manual had that auto missed → auto is MORE complete
- **Both-different emails**: 12 cases — auto tends to find PERSONAL emails, manual has COMPANY/alias emails
- **Both-different LinkedIn**: 20 cases — mostly trailing slash or `www.` prefix differences (format only)
- **Location error**: 1 case — Andrea Lewis wrong city/state in auto

### BOM Handling
Auto file had `\ufeff` prefix on `Name` header. Used `encoding='utf-8-sig'` in both reads.

### Python Stdlib Only (No Pandas)
Sandbox environment lacked pandas. Entire comparison done with `csv.DictReader` + dict lookups:
```python
with open(path, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
```

### Difference Classification Results
| Category | Email count | LinkedIn count |
|---|---|---|
| Both empty (no contact data) | 1,572 | 1,707 |
| Exact match | 8 | 0 |
| Auto found, Manual didn't | 329 | 169 |
| Manual found, Auto didn't | 64 | 89 |
| Both different values | 12 | 20 |

### Verdict Pattern
When auto_over >> auto_missed AND both-diff is mostly format differences: **auto is better**. Manual-only columns (Status, PIC) should be overlaid as enrichment, not treated as comparison failures.
