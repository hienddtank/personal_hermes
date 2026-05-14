# Travel Operations: Vietnamese Multi-Sheet Workflows

Common patterns when processing Vietnamese travel operation data (RUN TOUR style).

## Multi-Sheet XLSX with Inconsistent Column Names

RUN TOUR files often have 12 monthly sheets (T1.26–T12.26) where column names vary:

```python
# Dynamic column detection
date_col = None
for candidate in ['Travel Date', 'Travel Date\n(Formular)']:
    if candidate in df.columns:
        date_col = candidate
        break

sale_col = 'Sale'  # consistent across sheets
pax_col = 'Number Of Pax'
```

Common column name variants:
- `Travel Date` vs `Travel Date\n(Formular)` (line break in name)
- `Car ( Pick - up)` vs `Car (Pick-up)` vs `Car\n( Pick - up)` (spacing, line breaks)
- `Suplier` vs `Supplier` (typo)
- `Des` vs `DES` (case)
- Some sheets have extra `Unnamed: N` columns from merged cells

Always `df.columns.tolist()` before processing, then map dynamically.

## "Number Of Pax" Contains Passenger Names, Not Counts

Despite the column name, this field holds passenger **name(s)** for the booking, not a numeric count:

```
Michele Shore x 2 pax
Peter Eglinton Campbell x 2 pax
1. Candace Tabuchi\n2. Leslie Tabuchi
Cynthia Lee Armstrong (1956)\nJoe Walter Armstrong (1948)
```

### Counting actual passengers:

```python
def count_entries(pax_str):
    if pd.isna(pax_str) or pax_str == '':
        return 1
    lines = [l.strip() for l in pax_str.replace('\\n', '\n').split('\n') if l.strip()]
    return len(lines) if lines else 1
```

Parsing variations to handle:
- `Name x N pax` — single person, N = total confirmed
- `Name * N pax` — same format, `*` separator
- `Name (year)` — birth year in parens
- `1. Name\n2. Name` — sequential numbering
- `Name X N PAX` — uppercase X
- `Name\\nName` — literal `\n` vs actual newline

## One Trip Code = Multiple Itinerary Rows

Each booking (unique `Code`) has 1+ rows per day of itinerary (typically 30 days for a full tour month). Deduplicate to get 1 row per unique trip:

```python
# Each Code has ~30 itinerary rows
# Keep first row per code for trip metadata + combine passenger names
deduped = combined.groupby('Code', as_index=False).first()

# Collect ALL unique passenger entries per Code
pax_by_code = combined.groupby('Code')[pax_col].apply(
    lambda x: ' | '.join(x.dropna().unique())
).reset_index()
pax_by_code.columns = ['Code', 'All Passengers']
```

## Vietnamese Name Matching: Complete Approach

```python
import unicodedata

def strip_accents(s):
    """Remove ALL Vietnamese/Unicode diacritics for matching."""
    nfkd = unicodedata.normalize('NFKD', str(s))
    return ''.join(c for c in nfkd if not unicodedata.category(c).startswith('M'))

# Names to search for
sale_vals = df['Sale'].fillna('').apply(lambda x: strip_accents(x).strip().lower())
thang_mask = sale_vals.str.contains('thang', na=False)
lp_mask = sale_vals.str.contains('long.*pham', na=False)
```

## JSON as Source of Truth: Regenerating CSVs

Travel operation projects often have both JSON API responses AND derived CSVs. The JSON files are the **raw source of truth** — CSVs are regeneratable exports. **NEVER delete JSON files.**

### The extract_enquiries_to_csv.py Pattern

These projects commonly use a script that reads `all_enquiries.json` → flattens nested dicts → writes CSV:

```python
# Key characteristics:
# 1. Reads from Path("api_responses_xxx/all_enquiries.json")
# 2. Writes to Path("api_responses_xxx/all_enquiries.csv")
# 3. Flattens nested dicts with dot-notation keys (e.g., 'conversation.code')
# 4. Converts Unix timestamps to GMT+7 date strings (dd/mm/YYYY)
# 5. Handles both {"items": [...]} and [...] top-level JSON shapes
```

To regenerate CSVs after accidental overwrite:

```python
from pathlib import Path
folders = ['api_responses_tourradar', 'api_responses_tourradar_ra',
           'api_responses_tourradar_vtf']
for folder in folders:
    json_path = BASE / folder / 'all_enquiries.json'
    csv_path = BASE / folder / 'all_enquiries.csv'
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding='utf-8'))
        items = data if isinstance(data, list) else data.get('items', [])
        rows = [flatten_dict(item) for item in items]
        # ... format timestamps, write CSV with utf-8-sig ...
```

### Pre-Validation: Check JSONs Before Accepting Data Loss

If you filtered a CSV and overwrote the original, check for JSON source files FIRST:

```bash
ls api_responses_tourradar/all_enquiries.json
ls api_responses_tourradar_ra/all_enquiries.json
ls api_responses_tourradar_vtf/all_enquiries.json
```

If JSONs exist → regenerate CSVs. Save the user from data loss BEFORE reporting it.

### CSV Column Map (from JSON flattening)

When cross-referencing these CSVs with xlsx data, know which columns exist:

| CSV Column | Maps To | Used For |
|---|---|---|
| `booking_confirmation_id` | xlsx `Code` | Cross-reference key |
| `traveller_name` | Passenger info | Enrichment |
| `departure_at` | Trip date (GMT+7, dd/mm/YYYY) | Traveled filter |
| `completed` | Boolean | Traveled confirmation |
| `pax` | Passenger count | Verification |
| `tour.name` | Trip name | Metadata |

### CSV → XLSX Cross-Referencing

```python
# CSV ID maps to xlsx Code — normalize both to str
csv_codes = df_csv['booking_confirmation_id'].astype(str).str.strip()
xlsx_codes = df_xlsx['Code'].astype(str).str.strip()
matches = set(csv_codes) & set(xlsx_codes)

# Enrich xlsx with CSV traveller data
enriched = xlsx_data.merge(
    csv_data[['Code', 'traveller_name', 'departure_at', 'completed']],
    on='Code', how='left'
)
```

## Traveled vs Upcoming Trip Filter (with Direction Pitfall)

March 31 campaign cutoff: "March 31 minus 30 days" → departure date must be compared carefully.

```
cutoff = pd.Timestamp('2026-03-01')  # March 31 - 30 days
```

### ⚠️ Pitfall: Ambiguous Direction

When the user says **"if departure date is smaller than 31 march - 30, count as traveled"**:

- **"Smaller than [the cutoff]"** = departure < March 1 → **traveled** (completed before campaign)
- I initially interpreted this backwards as departure **≥** March 1 (recent/future)
- Always ask or test both directions when the wording is ambiguous!

```python
# CORRECT (typically): departure BEFORE cutoff = completed = traveled
traveled = df[df['Departure Date'] < cutoff]
upcoming = df[df['Departure Date'] >= cutoff]

# WRONG (my first attempt): would include future trips as "traveled"
# traveled = df[df['Departure Date'] >= cutoff]
```

### Verifying the Filter

After applying, sanity-check the date range:
```python
print(f"Traveled range: {traveled['Departure Date'].min()} to {traveled['Departure Date'].max()}")
# If max > cutoff, the direction is wrong — fix immediately.
```

## NEVER Overwrite Originals Without Backup

**CRITICAL PITFALL:** When filtering or transforming data, NEVER copy results back over original files. This permanently loses the source data, making it impossible to:

- Recover filtered-out entries later
- Cross-reference with transformed results
- Re-run transformations with different parameters

Always work on copies and keep originals intact:

```bash
# DO: work on copies
mkdir -p ALL/
cp originals/*.csv ALL/
python filter_script.py  # operates on ALL/ copies ONLY

# DON'T: overwrite originals
cp ALL/filtered.csv originals/all_enquiries.csv  # ← LOSES DATA
```

If originals were accidentally overwritten, the only recovery path is:
1. Check if backup copies exist elsewhere
2. Re-derive from related files (e.g., xlsx master if it's the source of truth)
3. Accept data loss and note it to the user

## Code Type Normalization: XLSX vs CSV Matching

When cross-referencing xlsx `Code` columns with CSV `booking_confirmation_id`:

```python
# Codes from xlsx may be integers, CSV IDs may be strings or floats
xlsx_codes = set(df_xlsx['Code'].astype(str).str.strip().unique())
csv_ids = set(df_csv['booking_confirmation_id'].astype(str).str.strip().unique())

# Match
matches = xlsx_codes & csv_ids
```

If match count = 0 when you expect matches:
- Verify both source files are unfiltered (not already processed)
- Check for type mismatches (int vs float vs string)
- Check for leading/trailing whitespace in IDs

## UTF-8 BOM for Vietnamese Excel Compatibility

Vietnamese-accented characters (ắ, ạ, ệ, etc.) render as garbage in Excel unless saved with BOM. Always use:

```python
df.to_csv('output.csv', index=False, encoding='utf-8-sig')
```

This is non-negotiable for Vietnamese-language data. User preference enforced.

## Full Pipeline: Extract → Dedupe → Filter → Export

```python
import pandas as pd
import unicodedata

def strip_accents(s):
    nfkd = unicodedata.normalize('NFKD', str(s))
    return ''.join(c for c in nfkd if not unicodedata.category(c).startswith('M'))

sheet_configs = {
    'T1.26': 'Sale', 'T2.26': 'Sale', 'T3.26': 'Sale', ...
}

cutoff = pd.Timestamp('2026-03-01')
all_trips = []

for sheet, sale_col in sheet_configs.items():
    df = pd.read_excel('file.xlsx', sheet_name=sheet)
    
    # Find date col dynamically
    date_col = next((c for c in ['Travel Date', 'Travel Date\n(Formular)'] if c in df.columns), None)
    if not date_col:
        continue
    
    # Match Vietnamese names
    sale_norm = df[sale_col].fillna('').apply(lambda x: strip_accents(x).strip().lower())
    mask = sale_norm.str.contains('thang|long.*pham', regex=True, na=False)
    matched = df[mask].copy()
    if len(matched) == 0:
        continue
    
    matched['Departure Date'] = pd.to_datetime(matched[date_col], errors='coerce')
    traveled = matched[matched['Departure Date'] < cutoff]  # or >= cutoff
    all_trips.append(traveled)

combined = pd.concat(all_trips, ignore_index=True)
deduped = combined.groupby('Code', as_index=False).first()
deduped.to_csv('output.csv', index=False, encoding='utf-8-sig')
```
