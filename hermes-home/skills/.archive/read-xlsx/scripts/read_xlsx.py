#!/usr/bin/env python3
"""
Read CSV and XLSX files.

Usage: python read_xlsx.py <file_path> [sheet_name]

Supports both .csv and .xlsx files automatically based on file extension.
"""

import sys
import os
from pathlib import Path

# Try to import required libraries
try:
    import pandas as pd
except ImportError:
    print("Error: pandas not installed. Run: pip install pandas openpyxl")
    sys.exit(1)


def read_file(file_path, sheet_name=None):
    """Read CSV or Excel file based on extension."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix == '.csv':
        # Read CSV file
        return pd.read_csv(file_path)
    elif suffix in ['.xlsx', '.xls']:
        # Read Excel file
        try:
            import openpyxl
        except ImportError:
            print("Error: openpyxl not installed. Run: pip install openpyxl")
            sys.exit(1)
        
        if sheet_name is None:
            # Default to first sheet
            xl = pd.ExcelFile(file_path)
            sheet_name = xl.sheet_names[0]
        
        return pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
    else:
        print(f"Unsupported file type: {suffix}")
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python read_xlsx.py <file_path> [sheet_name]")
        print("Supports .csv and .xlsx files")
        return 1
    
    file_path = sys.argv[1]
    sheet_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return 1
    
    try:
        df = read_file(file_path, sheet_name=sheet_name)
        
        if df is None:
            return 1
        
        # Print file type and info
        path = Path(file_path).suffix.lower()
        print(f"File: {file_path}")
        print(f"Type: {'CSV' if path == '.csv' else 'Excel'}")
        print(f"Shape: {df.shape[0]} rows x {df.shape[1]} columns\n")
        
        # Print all non-empty rows
        for idx, row in df.iterrows():
            # Filter out NaN values and convert to list
            data = [str(v) if pd.notna(v) else None for v in row.values]
            # Remove trailing None values
            while data and data[-1] is None:
                data.pop()
            
            if data:
                print(data)
        
        return 0
        
    except Exception as e:
        print(f"Error reading file: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())