# Keyword Search Across Multi-File Data

Search all text columns in multiple data files for a keyword (e.g., "BKK", "Hanoi", "luxury"), then break down hits by sales person, source, or category.

## Use Case

User asks: *"how many bkk of thang and lp in all of the files"* — they want a count of Bangkok tours across xlsx + CSVs, split by sales person.

## Pattern

```python
import pandas as pd
import re

# Load all data sources
xlsx = pd.read_csv('xlsx_rows.csv', low_memory=False)
enq = pd.read_csv('enquiries.csv', low_memory=False)

def bkk_mask(df):
    """Search ALL text columns for case-insensitive keyword."""
    mask = pd.Series(False, index=df.index)
    hits = {}
    pattern = r'(?i)\bbkk\b|bangkok'  # word boundary + case-insensitive
    
    for col in df.columns:
        try:
            m = df[col].astype(str).str.contains(pattern, na=False, regex=True)
            if m.sum() > 0:
                hits[col] = int(m.sum())
                mask = mask | m
        except:
            pass  # Skip non-text columns
    return mask, hits

# Apply to each data source
for label, df in [('XLSX', xlsx), ('Enquiries', enq)]:
    mask, hit_cols = bkk_mask(df)
    print(f"{label}: {mask.sum()} rows, columns: {hit_cols}")

# Breakdown by sales person
if 'Sale' in xlsx.columns:
    sale = xlsx['Sale'].fillna('').str.lower()
    for sp, pattern in [('Thang', 'thang'), ('Long Pham', r'long.*pham')]:
        is_sp = sale.str.contains(pattern, na=False)
        n = (mask & is_sp).sum()
        print(f"  {sp}: {n} BKK / {is_sp.sum()} total")

# For CSVs: match via email -> sales pools
# (see cross-campaign-email-matching.md for email pool loading)
enq_tagged = enq.merge(email_to_sales_map, on='email', how='left')
for sp in ['sales1 (Long Pham)', 'sales18 (Thang)']:
    n = (mask_e & enq_tagged['Match'].str.contains(sp, na=False)).sum()
    print(f"  {sp} (enq): {n}")
```

## Key Points

- Search ALL text columns (not just known ones like `tour.name`) — keywords appear in `ITINERARY`, `lastMessage.message`, `Hotel`, `Guide`, etc.
- Use word boundaries `\b` to avoid false matches (e.g., "BKK" in "BKK1234" not "BKKL")
- Always show WHICH columns had hits — helps validate the search
- Double-counting is OK (same row may hit in multiple columns) — report both the per-column breakdown and the combined row count
- The `select_dtypes(include='object')` trick is deprecated in pandas 3 — just iterate all columns and catch exceptions

## Expected Columns Where Keywords Appear

For Vietnamese tour data:
- ITINERARY / Iternity / Itinerary — tour route text
- Hotel — hotel names often include city
- Guide — guide notes sometimes mention cities
- Op — operator notes
- tour.name — tour package name
- lastMessage.message — enquiry conversation text

## Combining with Sales Person Breakdown

For xlsx data: use the `Sale` column with Vietnamese accent-stripped matching:
```python
import unicodedata
def strip_accents(s):
    nfkd = unicodedata.normalize('NFKD', str(s))
    return ''.join(c for c in nfkd if not unicodedata.category(c).startswith('M'))

sale_norm = df['Sale'].fillna('').apply(strip_accents).str.lower()
is_thang = sale_norm.str.contains('thang', na=False)
is_lp = sale_norm.str.contains(r'long.*pham', na=False)
```

For CSV data: use the email-matching pipeline from `cross-campaign-email-matching.md`.
