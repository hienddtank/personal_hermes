# Cross-Campaign Email Matching

Match enquiry/traveller emails against sales correspondents lists from other campaign folders.

## Context

Tour operators run monthly campaigns (`Campaign Apr B2C`, `Campaign_ Feb`, etc.). Each campaign folder has:
- **Enquiry CSVs** (TourRadar exports) with client `email`, `traveller_name`, `booking_confirmation_id`
- **Sales folders** (`sales1`, `sales18`, etc.) with `correspondents.csv` and `who_uses_which_email.xlsx` — the sales person's email history

Goal: tag enquiry emails with which sales person they've corresponded with.

## Data Sources

### Enquiry Side
- 3 CSV files: `tourradar_all_enquiries.csv`, `tourradar_ra_all_enquiries.csv`, `tourradar_vtf_all_enquiries.csv`
- Key columns: `email`, `traveller_name`, `departure_at`, `booking_confirmation_id`, `status`, `tour.name`
- `departure_at` is day-first format (DD/MM/YYYY or DD/MM/YYYY)
- Parse with `pd.to_datetime(df['departure_at'], dayfirst=True, errors='coerce')`

### Sales Email Pools
Located at `Campaign_ Feb/export_out/sales{id}/`:

**CSV/XLSX sources** (available for both sales folders):
- `correspondents.csv` — single column `email`
- `who_uses_which_email.xlsx` or `who_uses_which_email_v2.xlsx` — columns: `name`, `email`, `observations`, `sources_seen`

**JSON sources** (PREFERRED — extracted from actual email traffic, not manually compiled lists):
- `gmail_export.jsonl` — JSONL file (one JSON per thread) with fields: `from`, `to`, `cc`, `bcc`, `from_email`, `to_email`, `subject`, `date`, `body_text`, `thread_key`, etc. Extract `from_email`, `to_email`, and also regex-scan `from`, `to`, `cc`, `bcc` for embedded addresses.
- `maybe_client_threads.json` — dict with `emails` key (list of dicts, each has `email` field), `matched_clients` (count), `matched_messages` (list of dicts with `from`/`to`/`cc`/`bcc` fields)
- `auto_classifier_updates.json` — config only, no email data

**IMPORTANT**: `sales1/gmail_export.jsonl` is **empty** (0 bytes). Only sales18 has JSON email data (66MB, 43,938 threads). For sales1, fall back to CSV/XLSX.

**sales1** = Long Pham (5,835 from CSV/XLSX; no JSON data available)
**sales18** = Thang (1,074 from 43,938 JSON threads + maybe_client_threads.json)

Combine ALL sources (JSON + CSV + XLSX) per sales person for maximum coverage.

## Workflow

```python
import pandas as pd
import json
import re
import os

def extract_emails_from_text(text):
    """Extract email addresses from a text string (handles 'Name <email>' format)."""
    if not text or pd.isna(text):
        return set()
    return set(re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', str(text)))

# 1. Load email pools — JSON FIRST, fall back to CSV/XLSX
def load_email_pool(sales_dir):
    """Load all emails from a sales folder: JSONL + JSON + CSV + XLSX."""
    emails = set()
    
    # === JSON sources (preferred — actual email traffic) ===
    # a) gmail_export.jsonl (JSONL, one JSON object per thread)
    jsonl_path = os.path.join(sales_dir, 'gmail_export.jsonl')
    if os.path.exists(jsonl_path) and os.path.getsize(jsonl_path) > 0:
        with open(jsonl_path) as f:
            for line in f:
                try:
                    d = json.loads(line.strip())
                    for field in ['from', 'to', 'cc', 'bcc', 'from_email', 'to_email']:
                        emails.update(extract_emails_from_text(d.get(field, '')))
                except:
                    pass
    
    # b) maybe_client_threads.json (dict with structured email lists)
    mc_path = os.path.join(sales_dir, 'maybe_client_threads.json')
    if os.path.exists(mc_path):
        with open(mc_path) as f:
            mc = json.load(f)
        if 'emails' in mc:
            for entry in mc['emails']:
                if isinstance(entry, dict) and 'email' in entry:
                    emails.add(entry['email'].strip().lower())
        if 'matched_messages' in mc:
            for msg in mc['matched_messages']:
                for field in ['from', 'to', 'cc', 'bcc', 'from_email', 'to_email']:
                    if field in msg:
                        emails.update(extract_emails_from_text(msg[field]))
    
    # c) Thread JSONs in threads/ subfolder
    thread_dir = os.path.join(sales_dir, 'threads')
    if os.path.isdir(thread_dir):
        for fn in os.listdir(thread_dir):
            fp = os.path.join(thread_dir, fn)
            if os.path.isfile(fp) and fn.endswith('.json'):
                try:
                    with open(fp) as tf:
                        data = json.load(tf)
                        if isinstance(data, dict):
                            for field in ['from', 'to', 'cc', 'bcc', 'from_email', 'to_email']:
                                if field in data:
                                    emails.update(extract_emails_from_text(data[field]))
                except:
                    pass
    
    # === CSV/XLSX sources (fallback — manually compiled lists) ===
    # correspondents.csv
    corr_path = os.path.join(sales_dir, 'correspondents.csv')
    if os.path.exists(corr_path):
        corr = pd.read_csv(corr_path)
        emails.update(corr['email'].dropna().astype(str).str.strip().str.lower())
    
    # who_uses_which_email.xlsx (may be v2)
    for fname in ['who_uses_which_email_v2.xlsx', 'who_uses_which_email.xlsx']:
        fpath = os.path.join(sales_dir, fname)
        if os.path.exists(fpath):
            try:
                who = pd.read_excel(fpath)
                emails.update(who['email'].dropna().astype(str).str.strip().str.lower())
            except:
                continue
    
    # Clean: lowercase, strip, filter invalid
    return {e.strip().lower() for e in emails if '@' in e and len(e) < 100 and '.' in e.split('@')[-1]}

s1_emails = load_email_pool('sales1')   # Long Pham
s18_emails = load_email_pool('sales18')  # Thang

# 2. Load enquiries
enq = pd.read_csv('enquiries.csv', low_memory=False)
enq['_email'] = enq['email'].astype(str).str.strip().str.lower()

# 3. Tag each row
def tag_sales(email):
    e = str(email).strip().lower()
    if e in ('nan', ''): return 'no_match'
    in_s1 = e in s1_emails
    in_s18 = e in s18_emails
    if in_s1 and in_s18: return 'both'
    if in_s1: return 'sales1 (Long Pham)'
    if in_s18: return 'sales18 (Thang)'
    return 'no_match'

enq['Match'] = enq['email'].apply(tag_sales)
```

## Pitfalls

- **JSONL entries are dicts, not strings**: `maybe_client_threads.json` → `emails` is a list of `{"email": "...", "category": "...", ...}` dicts. Extract `entry['email']`, not `entry` directly.
- **Sales1 JSONL is empty**: `sales1/gmail_export.jsonl` is 0 bytes. For sales1, rely on `correspondents.csv` + `who_uses_which_email_v2.xlsx` only. This is normal — not all sales folders have exported email JSON.
- **Low match rate is expected**: Most enquiry emails are end-client travelers (gmail, yahoo, privaterelay.appleid.com). Sales correspondents are B2B contacts (agents, suppliers, partners). Typical match: 5-10% of enquiry emails.
- **BKK/regional queries need manual classification**: Use full-text scan across all columns (`'bkk' in row.lower()`) to find region-specific enquiries when there's no dedicated region column.
- **Overlap between sales pools**: ~670 emails are shared between sales1 and sales18 (e.g., `booking@tourradar.com`, internal addresses). Tag as `both` rather than splitting.
- **Email normalization**: Always lowercase + strip. Vietnamese emails sometimes have unexpected whitespace.
- **Encoding**: Use `utf-8-sig` for all reads/writes — Vietnamese email names contain diacritics.
- **FROM field parsing**: The `from` field in JSONL has format `"Name <email>"` (e.g., `Realistic Asia <res1@realisticasia.com>`). Regex `[\w.+-]+@[\w-]+\.[\w.-]+` extracts the email part. Same for `to`/`cc`/`bcc` which can contain multiple addresses.

## Output: Multi-Sheet Excel by Source

When the user wants matched emails split by enquiry source, output a single Excel workbook with:
1. **ALL Matched** — combined summary sheet
2. **TR-All Enquiries** — `Source == 'TR-All'` subset
3. **TR-RA Enquiries** — `Source == 'TR-RA'` subset
4. **TR-VTF Enquiries** — `Source == 'TR-VTF'` subset

```python
with pd.ExcelWriter('matched_emails_by_source.xlsx', engine='openpyxl') as writer:
    matched.to_excel(writer, sheet_name='ALL Matched', index=False)
    matched[matched['Source'] == 'TR-All'].to_excel(writer, sheet_name='TR-All Enquiries', index=False)
    matched[matched['Source'] == 'TR-RA'].to_excel(writer, sheet_name='TR-RA Enquiries', index=False)
    matched[matched['Source'] == 'TR-VTF'].to_excel(writer, sheet_name='TR-VTF Enquiries', index=False)
```

This keeps one shared overview sheet plus per-source drill-downs.

## Output Columns

Keep key columns only for the matched output:
`email`, `Match`, `traveller_name`, `departure_at`, `status`, `tour.name`, `pax`, `value`, `currency`, `completed`, `booking_confirmation_id`, `Source`

## Expected Ratio

| Pool | Size | Typical Match |
|------|------|---------------|
| sales1 (Long Pham) | ~5,800 | ~550 rows |
| sales18 (Thang) | ~1,100 | ~50 rows |
| Both | ~670 | ~3 rows |
| Total matched | — | ~600 / 8,500 enquiries (~7%) |
