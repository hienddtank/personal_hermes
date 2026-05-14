# Multi-Sheet Date-Cutoff Extraction Pattern

## When to use
Extracting all rows from a multi-sheet xlsx where a date column is before a cutoff, plus enrichment from separate CSVs. Common in travel operations: "give me all tours departing before March 1, 2026, regardless of sales person."

## Key Principles

1. **NO silent deduplication** — keep ALL rows unless user explicitly asks for unique codes
2. **NO silent filtering** — confirm cutoff, confirm scope (all sales people? specific ones?)
3. **Per-sheet date validation** — verify the date column actually contains dates
4. **Report orphans** — when merging xlsx + CSV, report unmatched counts from both sides
5. **Output separately** — xlsx and CSV have different schemas; save as separate files unless user asks to merge

## Pattern

```python
import pandas as pd
import os

xlsx_path = 'RUN TOUR 2026.xlsx'
cutoff = pd.Timestamp('2026-03-01')

# --- Step 1: Extract ALL rows with valid dates ---
sheet_configs = {
    'T1.26':  'Travel Date',
    'T2.26':  'Travel Date',
    # ... more sheets
}

all_rows = []
for sheet, date_col in sheet_configs.items():
    df = pd.read_excel(xlsx_path, sheet_name=sheet)
    if date_col not in df.columns:
        continue
    
    # Parse dates
    df['_parsed_date'] = pd.to_datetime(df[date_col], errors='coerce')
    
    # Validate: at least 50% of non-null values should parse as dates
    non_null = df[date_col].dropna()
    valid = df['_parsed_date'].notna().sum()
    if len(non_null) > 0 and valid < len(non_null) * 0.3:
        # T4.26 gotcha: "Travel Date" column contains names
        print(f"WARNING {sheet}: only {valid}/{len(non_null)} parsed as dates")
        continue
    
    # Filter
    pre = df['_parsed_date'] < cutoff
    df_pre = df[pre].copy()
    df_pre['Sheet'] = sheet
    df_pre['Source'] = 'xlsx'
    all_rows.append(df_pre)

xlsx_all = pd.concat(all_rows, ignore_index=True)

# --- Step 2: Load CSVs, filter same cutoff ---
csv_files = ['enquiries_a.csv', 'enquiries_b.csv']
csv_rows = []
for fp in csv_files:
    df = pd.read_csv(fp, low_memory=False)
    df['_dep'] = pd.to_datetime(df['departure_at'], dayfirst=True, errors='coerce')
    pre = df[df['_dep'] < cutoff].copy()
    pre['Source'] = os.path.basename(fp)
    csv_rows.append(pre)

csv_all = pd.concat(csv_rows, ignore_index=True)

# --- Step 3: Save (NO dedup!) ---
xlsx_all.to_csv('xlsx_rows.csv', index=False, encoding='utf-8-sig')
csv_all.to_csv('csv_rows.csv', index=False, encoding='utf-8-sig')

# --- Step 4: Report ---
print(f"XLSX: {len(xlsx_all)} rows (NO dedup)")
print(f"CSV:  {len(csv_all)} rows (NO dedup)")
```

## Pitfalls

### 1. Deduplication destroys data
Multi-sheet workbooks have the same code on multiple sheets (T1 + T2). These are NOT duplicates — they have different details. `groupby('Code').first()` collapses 5,210 rows into ~500 codes, losing 91%.

### 2. Date columns that aren't dates
Some "Travel Date" columns contain agent names, not dates. Always validate per-sheet before trusting `pd.to_datetime()` results. If <30% parse as dates, the column is mislabeled.

### 3. Different date formats across sheets
- T3.26 uses `'Travel Date\n(Formular)'` (has newline)
- Other sheets use `'Travel Date'`
- CSVs use `dayfirst=True` for DD/MM/YYYY format

### 4. Cutoff assumptions
A file named "RUN TOUR 2026" will have most tours in 2026. A cutoff of March 1 will correctly yield ~0 results for sheets T3-T12 (all March+). This is expected — report the 0s to confirm the filter is working.
