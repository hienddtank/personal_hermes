---
name: tabular-data
description: Tabular data workflows — reading/writing CSV/Excel, comparing datasets, cross-referencing records, and data enrichment. Use pandas, openpyxl, or stdlib csv for all spreadsheet operations.
---

# Tabular Data Workflows

Reading, writing, comparing, and cross-referencing CSV/Excel files.

## Quick Selection Guide

- **Read/Write CSV/Excel**: pandas, openpyxl patterns below
- **Compare two datasets**: Dataset comparison workflow
- **Cross-reference & enrich**: Matching records between files
- **Filter by domain**: Email domain filtering
- **Staged outreach (balanced tiers)**: Stratified round-robin distribution
- **Staged outreach (frequency spacing)**: Spread contacts by agency size with phase offsets

## Reading Files

```python
import pandas as pd
# CSV
df = pd.read_csv('file.csv', encoding='utf-8-sig')  # Always use utf-8-sig for BOM
# Excel
df = pd.read_excel('file.xlsx', engine='openpyxl')
```

## Writing Files

```python
# CSV
df.to_csv('output.csv', index=False, encoding='utf-8-sig')
# Excel
df.to_excel('output.xlsx', index=False, engine='openpyxl')
# Minimal XLSX (no pandas)
from openpyxl import Workbook
wb = Workbook(); ws = wb.active
ws.append(['Header1', 'Header2'])
ws.append(['val1', 'val2'])
wb.save('output.xlsx')
```

## CSV Cleaning & Renaming

```python
import csv
rename_map = {
    'contactFullName': 'Full Name',
    'id': None,  # Drop
    'isBlocked': None,  # Drop
}
with open('in.csv', encoding='utf-8-sig') as fin, open('out.csv', 'w', encoding='utf-8-sig', newline='') as fout:
    reader = csv.DictReader(fin)
    writer = csv.DictWriter(fout, fieldnames=[v for v in rename_map.values() if v], extrasaction='ignore')
    writer.writeheader()
    for row in reader:
        writer.writerow({new: row.get(old, '') for old, new in rename_map.items() if new})
```

## Email Domain Filtering

```python
# Include only specific domains
df[df['email'].str.contains('@gmail.com', case=False, na=False)]
# Exclude domains
exclude = ['spam.com', 'fake.org']
df[~df['email'].apply(lambda e: any(d in str(e) for d in exclude) if pd.notna(e) else False)]
```

## Dataset Comparison

Compare two datasets where one is ground truth. Measures per-column match rates, classifies differences.

```python
import csv
def load_csv(path):
    with open(path, 'r', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

# Build lookups by key
def build_lookup(rows, key_cols=['Name', 'Company']):
    lookup = {}
    for r in rows:
        key = tuple((r.get(c, '') or '').strip().lower() for c in key_cols)
        lookup[key] = {c: (r.get(c, '') or '').strip() for c in set(r.keys())}
    return lookup

auto_by_key = build_lookup(auto_rows)
manual_by_key = build_lookup(manual_rows)
common_keys = set(auto_by_key) & set(manual_by_key)

# Cell-level comparison
for key in common_keys:
    a, m = auto_by_key[key], manual_by_key[key]
    for col in shared_cols:
        av, mv = a.get(col, ''), m.get(col, '')
        if av == mv:
            matching += 1
        elif av == '':
            auto_missed += 1
        elif mv == '':
            auto_over += 1
        else:
            both_diff += 1
```

### Difference Categories
1. **Match** — identical values
2. **Auto missed** — auto empty, manual has data
3. **Auto over-claimed** — auto has data, manual empty
4. **Both different** — non-empty but different values

### Per-Column Breakdown
```python
for col in shared_cols:
    matches = sum(1 for k in common_keys if auto_by_key[k].get(col, '') == manual_by_key[k].get(col, ''))
    print(f"{col}: {matches}/{len(common_keys)} match ({matches/len(common_keys)*100:.1f}%)")
```

## Cross-Reference & Enrichment

Match records between two files with different scopes, enrich one with data from the other.

### Name Normalization
```python
import re
def normalize_name(name):
    if not name: return ''
    n = str(name).strip().lower()
    n = re.sub(r'\b(the|of|&|llc|inc|ltd|corp|co|group)\b', '', n)
    return re.sub(r'[\s_.,\-/]+', ' ', n).strip()
```

### Multi-Strategy Matching
1. **Name + Company exact** (HIGH confidence)
2. **Name-only with company scoring** (MEDIUM)
3. **Substring fallback** (LOW)

```python
# Build indices
nc_index = {}  # (norm_name, norm_company) -> [rows]
name_index = {}  # (first_word, last_word) -> [rows]

# Match with scoring
candidates = []
key = (normalize_name(name), normalize_name(company))
if key in nc_index:
    candidates.append((3, nc_index[key][0]))  # Score 3 = HIGH
# Name-only fallback
parts = normalize_name(name).split()
if len(parts) >= 2:
    for ha in name_index.get((parts[0], parts[-1]), []):
        score = 1
        if companies_match(company, ha.get('Company', '')):
            score += 2
        candidates.append((score, ha))
candidates.sort(key=lambda x: x[0], reverse=True)
```

## Multi-Sheet Excel Exploration

When dealing with multi-sheet workbooks, discover sheets and their structures first:

```python
import pandas as pd
xlsx = pd.read_excel('file.xlsx', sheet_name=None)  # Returns dict of {sheet_name: DataFrame}
for name, df in xlsx.items():
    print(f"Sheet: {name}, Shape: {df.shape}, Columns: {list(df.columns)}")
```

### Vietnamese Accent Normalization for Name Matching
When matching names across datasets with Vietnamese diacritics (Thắng vs thang, Phạm vs pham):

```python
def normalize_vietnamese(text):
    """Strip Vietnamese accents for case-insensitive matching."""
    import unicodedata
    t = str(text).strip().lower()
    # Decompose accented chars → base char + combining marks, drop combining marks
    nfkd = unicodedata.normalize('NFKD', t)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))

# Usage
df['sale_normalized'] = df['Sale'].fillna('').apply(normalize_vietnamese)
mask = df['sale_normalized'].str.contains('thang|long.*pham', regex=True, na=False)
```

### Date-Based Trip Completion Estimation
When trips have departure dates but no explicit "finished" status, estimate completion by adding max trip duration:

```python
from datetime import timedelta
today = pd.Timestamp.today()
max_trip_days = 30  # assume max 30-day trips
cutoff = today - timedelta(days=max_trip_days)

dep = pd.to_datetime(df['departure_at'], errors='coerce')
finished_mask = (dep <= cutoff) & dep.notna()
ongoing_mask = (dep > cutoff) & (dep <= today)
future_mask = dep > today
```

## Travel Operations: Multi-Sheet Vietnamese Workflows

For RUN TOUR style workbooks (monthly sheets, Vietnamese names, itinerary dedup):
→ See `references/travel-ops-vietnamese.md`

For xlsx + CSV merge with orphan/enquiry handling:
→ See `references/data-merge-with-orphans.md`

For date-cutoff extraction from multi-sheet xlsx + CSV (no dedup, per-sheet date validation):
→ See `references/multi-sheet-date-extraction.md`

For cross-campaign email matching (enquiry → sales correspondents):
→ See `references/cross-campaign-email-matching.md`

For keyword search across all text columns in multi-file data (e.g., "how many BKK of Thang"):
→ See `references/keyword-search-across-files.md`

For travel-industry company cross-reference matching (avoids false positive substring matches on generic names like "Travel", "Luxury"):
→ See `references/travel-company-cross-reference.md`

For fuzzy enrichment with fuzzywuzzy (company + name multi-strategy matching with thresholds for travel industry data):
→ See `references/fuzzy-enrichment-cross-reference.md`

For auto-detecting header rows in Excel files with summary/percentage pre-header rows:
→ Run `scripts/excel_detect_headers.py <file.xlsx> <sheet>` to inspect, then use the suggested `header=N`

For stratified staged outreach distribution (one contact per group, balanced tier mix across stages):
→ See `references/staged-outreach-distribution.md`

For cross-referencing buyer names against tens of thousands of contacts (token-indexed matching to avoid O(n×m) timeout):
→ See `references/token-indexed-name-crossreference.md`

### Quick Checklist for This Pattern
1. `df.columns.tolist()` — columns vary per sheet (line breaks, typos)
2. `strip_accents()` via unicodedata.NFKD — Vietnamese name matching
3. `groupby('Code').first()` — deduplicate itinerary rows (1 Code = 30+ day rows)
4. `Number Of Pax` may hold names, not counts — parse with `count_entries()`
5. Export with `encoding='utf-8-sig'` for Excel font compatibility

## Critical Pitfalls

### NEVER Overwrite Original Files
When filtering, transforming, or cleaning data, work on COPIES. Never write results back to the original file paths. This permanently destroys source data needed for cross-referencing, re-filtering with different parameters, or recovering filtered-out entries. Always: copy originals to a work directory → transform copies → save results to new files.

### BOM Characters
ALWAYS use `encoding='utf-8-sig'` when reading AND writing CSVs with Vietnamese/Unicode content. Without BOM, accented characters render as garbage in Excel.

### Column Index Mismatch
NEVER use positional indices. Always map by header name:
```python
# WRONG
ig = row[29]
# RIGHT
field_map = dict(zip(headers, row))
ig = field_map.get('Ig', '')
```

### Summary Rows Before Headers (CSV)
Business CSVs often have summary rows before actual headers. Scan for distinctive column names:
```python
header_idx = None
for i, row in enumerate(all_rows):
    if 'Contact Name' in row:
        header_idx = i; break
```

### Multi-Sheet Layout Variation

Different sheets may have different total column counts and different positions for the same-named columns. See `references/multi-sheet-layout-variation.md` for detection patterns, normalization approaches, and pitfalls (positional indexing breaks across sheets, large numeric IDs as scientific notation).

### Summary Rows Before Headers (Excel) — Multi-Row Pre-Headers
Business Excel files can have **multiple** pre-header rows before the actual column names:
- Row 0: Summary counts (Total, Protencial, Reached Out…)
- Row 1: Percentage values (0.349563, 0.216292…)
- Row 2: Empty row
- Row 3: **Actual headers** (Contact Name, Company name, Location…)

Using `header=0` gives numeric column names; `header=1` gives percentage values as columns; neither works.

```python
# Read raw to inspect structure
df = pd.read_excel('file.xlsx', sheet_name='SheetName', header=None)

# Scan rows 0-5 to find the first row containing actual column headers
# (a row with text labels, not percentages or empty cells)
header_row = None
for i in range(min(6, len(df))):
    # Count non-empty, non-numeric values — a header row has mostly text
    text_cols = sum(1 for j in range(len(df.columns))
                    if pd.notna(df.iloc[i].iloc[j]) and not str(df.iloc[i].iloc[j]).replace('.', '').isdigit())
    if text_cols >= 5:  # At least 5 meaningful text columns → likely the header row
        header_row = i
        break

# Re-read with correct header
if header_row is not None:
    df = pd.read_excel('file.xlsx', sheet_name='SheetName', header=header_row)
else:
    raise ValueError("Could not find header row in first 6 rows")

# Verify columns look right
print(df.columns.tolist()[:10])
```

### Column Count Inconsistency
Rows may have different column counts. Always pad/slice:
```python
padded = list(row)[:len(headers)] + [''] * max(0, len(headers) - len(row))
```

### Name Spelling Variations
- Truncated names, nicknames, title prefixes
- Use first+last word normalization as fallback
- Consider fuzzy matching (`difflib.get_close_matches`) for edge cases

### Stale Filters from Prior Sessions

When re-running a data pipeline from a previous session (or a script that worked before), NEVER silently reuse the same filter criteria — especially cutoff dates, status filters, or scope limits. The user's intent changes between runs. Always confirm:
- The date cutoff (or that NO cutoff is wanted)
- Whether "all" means the same thing as last time
- If the filter direction (before/after cutoff) is still correct

```python
# ❌ WRONG — blindly reusing last session's cutoff
cutoff = pd.Timestamp('2026-03-01')  # was this for their campaign? this request?
traveled = df[df['Departure Date'] < cutoff]

# ✅ RIGHT — ask or state the filter, let user correct
# "Filtering to departure < March 3 2026 — is this the right cutoff?"
```

### Silent Deduplication (LOSSY by Default)

**NEVER deduplicate by Code/ID unless the user explicitly asks for unique entries.** The most common request in multi-sheet extraction is "give me all the rows" — but scripts naturally gravitate toward `groupby('Code').first()` because it produces cleaner output. This silently discards 90%+ of data:

```python
# ❌ WRONG — collapses 5,210 rows into 487 unique codes without asking
xlsx_dedup = xlsx_filtered.groupby('Code', as_index=False).first()

# ✅ RIGHT — keep ALL rows, let the user decide if they want dedup later
xlsx_all = pd.concat(all_sheets, ignore_index=True)
xlsx_pre_cutoff = xlsx_all[xlsx_all['Departure Date'] < cutoff]
# Don't groupby. Don't deduplicate. Report row counts.
```

**Why this happens:** multi-sheet workbooks often have the same code appearing on multiple sheets (T1 + T2 both have rows for code 22365). The rows are NOT duplicates — they have different details per sheet. The script's reflex to "deduplicate by code" destroys this data.

**Always report BOTH counts:**
```
XLSX rows pre-cutoff: 5,210 (dedup to 487 unique codes — dedup loses 91% of rows)
```

### Date Column Misdirection

Some Excel sheets have a column named "Travel Date" that actually contains **names, not dates** (e.g., T4.26 in Vietnamese tour workbooks). Always spot-check parsed values per sheet:

```python
for sheet in sheets:
    dates = pd.to_datetime(df[date_col], errors='coerce')
    valid = dates.notna().sum()
    if valid < len(df) * 0.5:  # Less than 50% parsed as dates
        print(f"WARNING: {sheet} date column only {valid}/{len(df)} valid — checking raw values")
        print(f"  Sample: {df[date_col].dropna().head(5).tolist()}")
        # T4.26 example: ['Uyên Khang Nguyên', 'Trường An SGN', 'RA', ...]
```

### Orphan Rows in Multi-Source Merges

When merging two datasets (e.g., xlsx master + CSV enquiries), **always report unmatched row counts from BOTH sides** and ask the user whether to:
1. Keep only matched rows (inner join)
2. Keep all xlsx rows + CSV matches (left join)
3. Keep all CSV rows + xlsx matches (right join)
4. Keep everything, marking orphans with a source column

```python
# After merge, report:
print(f"XLSX codes: {len(xlsx_codes)}, matched to CSV: {n_matched}, unmatched: {n_orphan}")
print(f"CSV rows: {len(csv_rows)}, matched to xlsx: {n_csv_matched}, orphans: {n_csv_orphan}")
# THEN ask user: "Keep orphans? Separate file or same file with flag?"
```

Never silently discard unmatched rows. The user may need them for a different analysis.

### NEVER Trust `read_file` Display Characters in `patch` Search Strings

When you read a file with `read_file`, the output format is:

```
     1|First Name,Last Name,Email Address
     2|Sofia,Sobral,sofiasobral@example.com
```

The `|` between the line number and content is a **display-only separator** — it is NOT part of the actual file. When using `patch`, if you accidentally include `|` in your search string (e.g., matching against `|Sofia,Sobral` instead of `Sofia,Sobral`), the patch may:
- Match a line that already has an extra `|` from a previous bad patch (chain corruption)
- Fail silently if the exact pattern doesn't exist
- Accidentally add/remove the `|` character in the file content

**Always verify the raw content before patching.** For CSVs, use Python to read and print lines, then match against actual content:
```python
# ✅ SAFE — read with Python to see real content
with open('file.csv') as f:
    for i, line in enumerate(f):
        if 'KARP' in line or 'NAVONE' in line:
            print(f"Line {i+1}: [{line.rstrip()}]")  # No | prefix
```

If a patch seems to corrupt formatting (missing commas, extra pipes, missing lines), revert and switch to Python-based editing.

### UTF-8 Replacement Characters (U+FFFD / mojibake)
When reading a CSV and seeing `�` in names or text fields, the file contains literal U+FFFD replacement characters — usually from a previous encoding conversion where non-ASCII bytes were invalid UTF-8 and got swapped to the replacement char. **Reading with `encoding='utf-8-sig'` will not fix it.** You must work at the raw byte level.

**Diagnosis:** Replace the file read with raw binary mode and count `\xef\xbf\xbd` (UTF-8 encoding of U+FFFD):
```python
with open('file.csv', 'rb') as f:
    raw = f.read()
repl_count = raw.count(b'\xef\xbf\xbd')
print(f"Found {repl_count} replacement characters")
# Find context around each one:
for pos in [i for i in range(len(raw)) if raw[i:i+3] == b'\xef\xbf\xbd']:
    line_start = raw.rfind(b'\n', 0, max(0, pos-100)) + 1
    line_end = raw.find(b'\n', pos)
    print(raw[line_start:line_end].decode('utf-8', errors='replace'))
```

**Fix:** Identify what each replacement character originally was from context (email address, name patterns, cultural/linguistic clues), then do binary-level `bytes.replace()`:
```python
with open('file.csv', 'rb') as f:
    raw = f.read()

repl = b'\xef\xbf\xbd'  # U+FFFD in UTF-8

# Fix each known corruption — use proper UTF-8 byte sequences for target chars
fixes = [
    (b'Tain' + repl, b'Taina'),          # Context: Brazilian Portuguese name
    (b'Lud' + repl + b'mila', b'Ludmila'),  # Email confirms no accent
    (b'M' + repl + b'ller', b'M\xc3\xbcller'),  # German ü
    (b'Bar' + repl + b'o', b'Bar\xc3\xa3o'),   # Portuguese ão
    (b'Ta' + repl + b'se', b'Taise'),       # Japanese name, email confirms
    (b'Fran' + repl + b'oise', b'Fran\xc3\xa7oise'),  # French ç
]

new_raw = raw
for old, new in fixes:
    new_raw = new_raw.replace(old, new)

with open('file.csv', 'wb') as f:
    f.write(new_raw)

# Verify
assert repl not in new_raw, f"Still {new_raw.count(repl)} replacement chars remain!"
```

**Common patterns to watch for (from travel industry data):**
- German names: ü → `\xc3\xbc`, ö → `\xc3\xb6`, ä → `\xc3\xa4`
- Portuguese (Brazil): ã → `\xc3\xa3`, õ → `\xc3\xb5`, ç → `\xc3\xa7`, á/é/í/ó/ú → `\xc3\xa1/\xc3\xa9/\xc3\xad/\xc3\xb3/\xc3\xba`
- French names: ç → `\xc3\xa7`, è/ê/é/ë → `\xc3\xa8/\xc3\xaa/\xc3\xa9/\xc3\xab`

→ See `references/mojibake-diagnostic.md` for the full diagnostic guide.

### Bash & Operator in Inline Python

When writing pandas expressions in bash `python3 -c "..."`, the `&` operator (e.g., `df['A'].notna() & df['B'].notna()`) is interpreted by bash as a **backgrounding directive**, causing silent failures or truncated commands. Never use raw `&` in `-c` strings:

```bash
# ❌ WRONG — bash eats the &, command breaks silently
python3 -c "import pandas as pd; mask = df['A'].notna() & df['B'].notna()"

# ✅ RIGHT — write to a temp script file instead
python3 /tmp/check.py
```

This affects **all** skills that use pandas in inline terminal calls, not just tabular-data.

### Python Environment: pandas Not in Default venv

The default `python3` resolves to `/opt/venv/bin/python3` which does NOT have `pip` installed and may lack `pandas`. Use the system Python instead:

```bash
# ❌ May fail with "No module named 'pandas'"
python3 -c "import pandas"
python3 /tmp/script.py

# ✅ System Python has pandas pre-installed
/usr/local/bin/python3.11 -c "import pandas"
/usr/local/bin/python3.11 /tmp/script.py
```

If you need to install packages, use `pip` (which installs to system Python) or write scripts that run via `/usr/local/bin/python3.11`. For complex scripts (>20 lines), always write to a temp file and run with the system Python — never use inline `python3 -c` for multi-statement pandas code (also avoids bash `&` operator issues).

### Combined Codes in Single Cells (e.g., "83202 + 83203")

Complaint lists, merged records, or manually-edited spreadsheets sometimes combine multiple IDs into one cell with separators like `+`, `,`, or spaces. Naive `int()` conversion fails:

```python
# ❌ WRONG — crashes on "83202 + 83203"
complained_codes.add(int(float(code)))  # ValueError

# ✅ RIGHT — extract all numeric IDs with regex
import re
def extract_codes(value):
    if pd.isna(value): return []
    return [int(n) for n in re.findall(r'\d+', str(value))]

# Usage: flatten combined codes into a set
all_codes = set()
for _, row in complaints.iterrows():
    all_codes.update(extract_codes(row['Code']))
```

**Watch for:** codes with suffixes like "80553 - A" (versioned entries). Use `re.match(r'(\d+)', str(code))` to extract the numeric prefix while preserving the full string if needed.

### Headerless Excel Files

Some business spreadsheets have NO header row — data starts at row 0 with no column labels. `pd.read_excel()` defaults to `header=0`, which incorrectly treats the first data row as column names:

```python
# ❌ WRONG — first row becomes column names
df = pd.read_excel('file.xlsx')  # header=0 by default

# ✅ RIGHT — read without headers, then assign manually or inspect
df = pd.read_excel('file.xlsx', header=None)
print(df.head())  # Inspect to understand column structure
# If you know the columns:
df.columns = ['Code', 'Type', 'Sales Person', ...]
```

**Diagnosis:** If `df.columns` contains mixed data types (numbers, text fragments) that look like actual values rather than labels, you're reading a headerless file. Always inspect row 0 before assuming it's a header.

### Setting New Columns with `df.at[]` — Must Initialize First

When setting new columns using `df.at[idx, 'col'] = value`, the column must exist before the first assignment. Otherwise pandas raises a `KeyError`:

```python
# ❌ FAILS on first write — column doesn't exist yet
for idx in df.index:
    df.at[idx, 'new_col'] = some_value  # KeyError: 'new_col'

# ✅ Initialize columns before the loop
for col in ['new_col', 'another_col']:
    if col not in df.columns:
        df[col] = ''  # or pd.NA for nullable
for idx in df.index:
    df.at[idx, 'new_col'] = some_value
```

Alternative: use `df['new_col'] = values` with a pre-built series instead of row-by-row assignment.

### Contact Directory vs Company List — Domain Extraction

When cross-referencing against a data source that looks like company data but is actually an **individual contact directory** (no Company column, or Company column is all NaN), extract company information from email domains instead:

```python
# Diagnose: check if Company column is empty
if df['Company'].isna().all():
    print("WARNING: No company names — this is a contact directory")
    # Extract domain-based identifiers from emails
    df['domain'] = df['Email'].str.extract(r'@([^\.]+)')\
                                .str.lower()
    print(f"Unique domains: {df['domain'].unique()}")

# Match buyer companies against email domain keywords
def domain_matches_company(domain, company_name):
    """Check if domain keywords appear in the company name."""
    if pd.isna(domain) or pd.isna(company_name): return False
    words = str(domain).replace('-',' ').replace('_',' ').split()
    norm = str(company_name).lower()
    return any(len(w) > 3 and w in norm for w in words)
```

**Workflow:**
1. Check if Company column is populated — if not, pivot to domain extraction
2. Extract email domains, deduplicate, map to company names (preferrednaples.com → Preferred Travel Naples)
3. Match buyer companies against domain tokens using substring matching with minimum token length (>3 chars)
4. Also attempt name matching between buyer names and contact names as a secondary strategy
5. Report matches separately: "domain-based" vs "name-based" for confidence tracking

**Pitfall:** Domain matching produces lower-confidence results than company-name matching. A domain like `gmail.com` or `yahoo.com` is useless; only org-specific domains produce meaningful matches. Always filter out generic providers.

### Travel Industry Company Name False Positives

When matching company names where **both datasets are from the travel industry**, substring matching produces many false positives because words like "Travel", "Luxury", "Adventures", "Group" appear everywhere. Example: "HE Travel" matches "The Travel Bus Co" simply because both contain "travel".

**Mitigations:**
1. **Require minimum token overlap, not just containment.** Both strings must share at least one non-stopword token, and the shorter string should be ≥ 3 tokens long to avoid single-word noise matches.
2. **After finding substring matches, manually review or filter by length ratio.** A match where one company name is only 1-2 words and the other is 4+ words is almost certainly noise unless there's a clear parent/brand relationship.
3. **Always report match quality (exact / high-confidence / partial) separately.** Never combine partial matches into the "matched" set without labeling them. Let the user decide what to keep.
4. **When in doubt, prefer zero matches over noisy false positives.** It's better to miss a real match than flood results with noise — users can manually review a small list of ambiguous cases instead of filtering through dozens of false positives.

```python
# Example: safe substring matching that avoids travel-industry noise
STOPWORDS = {'travel', 'luxury', 'group', 'agency', 'adventures', 'tours', 'tourism', 'vacations'}

def safe_substring_match(name_a, name_b, min_tokens=3):
    """Only consider substring match if it's substantive, not just shared industry words."""
    a, b = set(str(name_a).strip().lower().split()), set(str(name_b).strip().lower().split())
    # Skip trivial matches on short names or single-word substrings
    if len(a) < min_tokens or len(b) < 2:
        return False
    # Must share at least one non-stopword token
    shared = (a & b) - STOPWORDS
    if not shared:
        return False
    # One must contain the other as a string
    a_str, b_str = ' '.join(a), ' '.join(b)
    return a_str in b_str or b_str in a_str
```