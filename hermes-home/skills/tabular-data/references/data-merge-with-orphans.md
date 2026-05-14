# Data Merge with Orphan Handling

Pattern from Vietnamese travel ops: xlsx master (Thang/LP codes) + enquiry CSVs (TourRadar).

## Scenario

- **XLSX**: 12 monthly sheets, ~291 unique booking codes (Thang/LP only), multi-row itineraries
- **CSVs**: 3 files from TourRadar API (`all_enquiries`, `ra_all_enquiries`, `vtf_all_enquiries`), ~10K rows total
- **Goal**: Combine xlsx codes with CSV enquiry data, filtered by departure date

## Key Steps

### 1. Always ask about cutoff BEFORE running

```python
# The cutoff date changes between sessions — never hardcode from previous run
cutoff = pd.Timestamp('2026-03-03')  # CONFIRM with user first
```

### 2. Extract xlsx codes (Vietnamese name matching)

```python
import unicodedata
def strip_accents(s):
    nfkd = unicodedata.normalize('NFKD', str(s))
    return ''.join(c for c in nfkd if not unicodedata.category(c).startswith('M'))

mask = df['Sale'].fillna('').apply(lambda x: strip_accents(x).strip().lower())
thang = mask.str.contains('thang', na=False)
lp = mask.str.contains('long.*pham', na=False)
```

### 3. Load ALL CSV data, filter by departure_at

```python
df['_dep'] = pd.to_datetime(df['departure_at'], dayfirst=True, errors='coerce')
before_cutoff = df[df['_dep'] < cutoff]
```

### 4. Report orphan counts BEFORE deciding output

```python
xlsx_codes = set(xlsx_dedup['Code'].unique())
csv_codes = set(csv_all['Code'].unique())

matched = xlsx_codes & csv_codes
xlsx_orphans = xlsx_codes - csv_codes
csv_orphans = csv_codes - xlsx_codes

print(f"XLSX codes: {len(xlsx_codes)}")
print(f"  Matched to CSV: {len(matched)}")
print(f"  No CSV data: {len(xlsx_orphans)}")
print(f"CSV rows: {len(csv_all)}")
print(f"  Matched to xlsx: {len(csv_all[csv_all['Code'].isin(matched)])}")
print(f"  Orphans (no xlsx): {len(csv_all[~csv_all['Code'].isin(xlsx_codes)])}")
```

### 5. Let user choose orphan handling

Options:
- **Separate file** (recommended for large orphans): `orphan_enquiries_before_mar3.csv`
- **Same file with flag column**: add `Type = 'CSV Only'` for orphans
- **Discard**: only if user explicitly says so

### 6. Output both files

```python
# Main: xlsx codes enriched with CSV data
xlsx_dedup.to_csv('main_output.csv', index=False, encoding='utf-8-sig')

# Orphans: CSV rows with no xlsx match (if user wants them)
orphan_out[['Code', 'departure_at', 'status', 'traveller_name', 'email']].to_csv(
    'orphan_enquiries.csv', index=False, encoding='utf-8-sig'
)
```

## Column Cross-Reference (TourRadar CSV → RUN TOUR xlsx)

| CSV Column | xlsx Column | Notes |
|---|---|---|
| `booking_confirmation_id` | `Code` | Primary key for matching |
| `departure_at` | `Travel Date` | DD/MM/YYYY format, dayfirst=True |
| `traveller_name` | `Number Of Pax` | CSV has individuals, xlsx has grouped names |
| `completed` | — | CSV-only: True if trip finished |
| `status` | — | CSV-only: enquiry status |
| `tour.name` | — | CSV-only: tour name |
| `pax` | — | CSV-only: numeric passenger count |

## Pitfall: Number Of Pax is Names, Not Counts

Despite the column name, `Number Of Pax` in RUN TOUR xlsx contains passenger NAMES, not numeric counts. To count passengers, split by newlines:

```python
def count_entries(pax_str):
    if pd.isna(pax_str) or not pax_str.strip():
        return 1
    lines = [l.strip() for l in pax_str.replace('\\n', '\n').split('\n') if l.strip()]
    return len(lines) if lines else 1
```
