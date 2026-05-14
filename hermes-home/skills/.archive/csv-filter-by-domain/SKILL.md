---
name: csv-filter-by-domain
description: Filter CSV/Excel files by email domain (include/exclude specific domains) and export to separate files.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [csv, excel, filtering, data-cleaning]
---

# CSV Filter by Email Domain Skill

## Purpose
Filter rows in CSV/Excel files based on email domains (e.g., exclude @trevello.com or @tpi.ca) and export to separate output files.

## Usage
Call this skill when you need to filter a CSV/Excel file by email domain patterns.

## Steps
1. Read the input CSV/Excel file using pandas
2. Identify columns containing email addresses
3. Filter rows based on included/excluded domains
4. Export filtered and removed rows to separate output files

## Code Pattern
```python
import pandas as pd

# Read the file
df = pd.read_csv('/path/to/input.csv')

# Define domains to exclude
exclude_domains = ['@trevello.com', '@tpi.ca']

# Filter out rows with excluded domains
mask = ~df['email_column'].str.contains('|'.join(exclude_domains), na=False)
filtered_df = df[mask]
removed_df = df[~mask]

# Export to CSV/Excel
filtered_df.to_csv('/path/to/output_filtered.csv', index=False)
removed_df.to_csv('/path/to/output_removed.csv', index=False)
```

## Notes
- Automatically detects email columns (columns with @ in values)
- Can handle multiple domains to exclude
- Exports both filtered and removed rows to separate files
- Works with CSV and Excel (.xlsx, .xls) formats

## Example
User: "Filter out rows with @trevello.com and @tpi.ca from D:\mkt\python\B2B cleaning 2\Agency Database - Nhung.csv"
Agent: Reads file, filters out those domains, exports filtered and removed rows to separate files.