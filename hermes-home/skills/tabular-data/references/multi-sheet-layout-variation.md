# Multi-Sheet Excel with Layout Variation

## Problem

Multi-sheet workbooks may have different column layouts per sheet — even when they share the same semantic columns. Columns can shift position, and some sheets may have more or fewer total columns than others.

### Pattern: Header-Only Difference (No Pre-Header Stats)

Some sheets start directly with headers; others have summary stats rows before headers.

```python
# Per-sheet layout map — build dynamically by inspecting row 4
def detect_layout(sheet, row=4):
    """Detect column mapping for a sheet by reading its header row."""
    col_map = {}
    for c in range(1, 50):
        val = ws.cell(row=row, column=c).value
        if val:
            col_map[val] = c
    return col_map

# Usage per sheet:
layout = detect_layout(ws)
ig_col = layout.get('Ig')  # May be 29 on some sheets, 30 on others
```

### Pattern: Different Total Column Counts

One source may have 37 columns (Full Database type), another 31 (event-sheet type). When merging rows across sheets, always normalize to a canonical schema:

```python
# Canonical output columns
CANONICAL_COLS = ['Source', 'Contact Name', 'Company name', ..., 'Ig', 'Phone number']

def normalize_row(row_data, canonical_cols):
    """Pad or slice row to match canonical column order."""
    # Pad if source has fewer columns
    while len(row_data) < len(canonical_cols):
        row_data.append('')
    return row_data[:len(canonical_cols)]
```

## Common Pitfalls

- **Positional indexing breaks across sheets.** `row[29]` may be `Ig` on one sheet and `Facebook` on another. Always map by header name.
- **Merged cells produce None for offset columns.** Use `ws[cell.coordinate].value` after checking `cell.value is not None`.
- **Data rows before headers in some sheets.** Full Database type has stats at rows 1–3, headers at row 4, data at row 5+. Other sheet types may start data at row 2. Inspect each sheet individually.
- **Large numeric IDs stored as floats.** `4407463565804` may appear as scientific notation (`5.51e+16`) in some tools. Use `int(float(val))` to recover.
