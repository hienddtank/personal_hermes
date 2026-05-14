#!/usr/bin/env python3
"""Auto-detect header row in Excel sheets that have summary rows at the top.

Usage:
  python excel_detect_headers.py <xlsx_file> <sheet_name> [--rows 6]

Prints column names from detected header row. If no clear header found, shows raw content of first N rows.

Works for business Excel files where the header may be preceded by:
- Summary count rows (Total, Protencial, etc.)
- Percentage rows (0.349563, 0.216292…)
- Empty rows
"""
import argparse
import sys

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is required. Run: pip install pandas openpyxl")
    sys.exit(1)


def find_header_row(df, max_rows=6):
    """Scan first N rows to find the header row.

    A header row has mostly text values (not pure numbers, not empty).
    Returns the index of the detected header row or None.
    """
    for i in range(min(max_rows, len(df))):
        if pd.isna(df.iloc[i]).all():
            continue  # Skip completely empty rows

        text_cols = 0
        numeric_cols = 0
        for j in range(len(df.columns)):
            val = df.iloc[i].iloc[j]
            if pd.isna(val):
                continue
            val_str = str(val).strip()
            if not val_str:
                continue

            # Check if it looks like a header label (text)
            is_numeric = val_str.replace('.', '').replace(',', '').replace('%', '').isdigit()
            if is_numeric:
                numeric_cols += 1
            else:
                text_cols += 1

        # A header row should have more text labels than pure numbers
        total = text_cols + numeric_cols
        if total > 0 and text_cols >= max(5, total * 0.4):
            return i, text_cols

    return None, 0


def main():
    parser = argparse.ArgumentParser(description="Detect header row in Excel files")
    parser.add_argument("xlsx_file", help="Path to the .xlsx file")
    parser.add_argument("sheet_name", help="Sheet name to inspect")
    parser.add_argument("--rows", type=int, default=6, help="Number of top rows to scan (default: 6)")
    args = parser.parse_args()

    df = pd.read_excel(args.xlsx_file, sheet_name=args.sheet_name, header=None)

    idx, text_count = find_header_row(df, max_rows=args.rows)

    if idx is not None:
        print(f"HEADER ROW DETECTED at index {idx} ({text_count} text columns)")
        print("Columns:")
        for j, col in enumerate(df.columns):
            val = str(df.iloc[idx].iloc[j]) if pd.notna(df.iloc[idx].iloc[j]) else ''
            print(f"  [{j}]: {val}")
        print()
        print(f'Usage: header={idx}')
    else:
        print("NO CLEAR HEADER ROW FOUND in first", args.rows, "rows")
        print("\nRaw content:")
        for i in range(min(args.rows, len(df))):
            vals = [str(df.iloc[i].iloc[j])[:40] if pd.notna(df.iloc[i].iloc[j]) else ''
                    for j in range(min(15, len(df.columns)))]
            print(f"  Row {i}: {vals}")


if __name__ == '__main__':
    main()
