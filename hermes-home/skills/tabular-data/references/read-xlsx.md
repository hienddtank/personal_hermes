---
name: read-xlsx
description: Read and write CSV/Excel files using Python (pandas, openpyxl). Covers reading/writing xlsx/csv, conditional column logic, adding columns with mappings, and filtering by domain. Includes minimal XLSX creation patterns and CSV email-domain filtering.
version: 2.0.0
author: Hermes Agent
tags: [csv, excel, xlsx, data-extraction, spreadsheet, openpyxl, pandas]
---

# Read/Write XLSX/CSV Skills

## Purpose
Read and extract data from CSV and Excel (.xlsx) files using Python's pandas library. Also covers minimal XLSX creation patterns and CSV email-domain filtering.

## Prerequisites
```bash
pip install pandas openpyxl
```

## Reading Files

### CSV files
```python
import pandas as pd
df = pd.read_csv('/path/to/file.csv')
```

### Excel files
```python
df = pd.read_excel('/path/to/file.xlsx', sheet_name='Sheet1', engine='openpyxl')
# If no sheet specified, defaults to first sheet
```

### Iterating through rows
```python
for idx, row in df.iterrows():
    print(row.values.tolist())
```

## Adding Columns with Conditional Logic

When adding new columns based on conditional logic:

```python
import pandas as pd

def assign_id(name, birth_year=None):
    name_lower = name.lower() if isinstance(name, str) else ''
    
    # Specific checks
    if 'đỗ thị khánh ly' in name_lower and str(birth_year).replace('/','') == '2003':
        return 'S07'
    if 'bùi thị phương linh' in name_lower:
        return 'S08'
    
    return ''

for idx, row in df.iterrows():
    new_id = assign_id(row['name'], row.get('birth_year'))
    df.at[idx, 'new_column'] = new_id

df.to_excel('/path/to/output.xlsx', index=False)
```

## Minimal XLSX Creation (openpyxl)

For creating minimal .xlsx files when pandas openpyxl engine isn't available:

```python
from openpyxl import Workbook
wb = Workbook()
ws = wb.active
ws['A1'] = 'Header 1'
ws.append(['value1', 'value2'])
wb.save('/path/to/output.xlsx')
```

See references/minimal-xlsx-creation.md for more patterns.

## CSV Filtering by Email Domain

Filter CSV files to include only specific email domains or exclude others:

```python
import pandas as pd

df = pd.read_csv('input.csv')
# Include only Gmail addresses
filtered = df[df['email'].str.contains('@gmail.com', case=False, na=False)]

# Exclude spam domains
exclude_domains = ['spam.com', 'fake.org']
filtered = df[~df['email'].apply(lambda e: any(d in str(e) for d in exclude_domains) if pd.notna(e) else False)]
```

See references/csv-domain-filtering.md for complete patterns.

## CSV Column Renaming & Cleaning

When CSV columns use machine-friendly names (snake_case, API-style prefixes, UUIDs, system flags), clean them for human readability:

```python
import csv

rename_map = {
    # Keep and rename
    'category__buyer_s_client_location': 'Client Location',
    'contactFullName': 'Full Name',
    'name': 'Company Name',
    # Drop (set to None)
    'id': None,                        # UUID
    'isBlocked': None,                 # system flag
    'contactProfileImage': None,       # image URL
    'meetingPreferenceParentId': None, # UUID
}

new_fields = [v for v in rename_map.values() if v is not None]

with open('input.csv', newline='', encoding='utf-8-sig') as fin, \
     open('output_clean.csv', 'w', newline='', encoding='utf-8') as fout:
    reader = csv.DictReader(fin)
    writer = csv.DictWriter(fout, fieldnames=new_fields, extrasaction='ignore')
    writer.writeheader()
    for row in reader:
        clean = {new: row.get(old, '') for old, new in rename_map.items() if new is not None}
        writer.writerow(clean)
```

**Common columns to drop:**
- UUIDs / internal IDs (`id`, `parentId`, `uuid`)
- System flags (`isBlocked`, `isPreference`, `isArchived`)
- Raw URLs for images/logos (`logo`, `avatarUrl`, `contactProfileImage`)
- Internal foreign keys not meaningful to end users

**Common rename patterns:**
- `category__buyer_s_*` → strip prefix, title-case (e.g., "Company Type")
- `contactFullName` → "Full Name"
- `linkedInUrl` / `instagramUrl` → "LinkedIn" / "Instagram"
- `description` → "Company Description" (disambiguate from contact bio)

**Always:** inspect one row first (`head -1` or read first row) to confirm column meanings before deciding what to drop.

## Notes
- File type auto-detected by extension (.csv or .xlsx/.xls)
- For Excel without specified sheet, defaults to first sheet
- Install `pandas` and `openpyxl` before reading/writing
