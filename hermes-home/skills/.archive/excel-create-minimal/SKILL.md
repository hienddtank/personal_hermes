---
name: Excel Create Minimal
description: Create minimal XLSX files from data when standard Excel libraries (openpyxl, xlwt) are unavailable. Uses Python's zipfile and XML libraries to construct a valid Excel file structure.
version: 1.0
author: Hermes Agent
---

# Excel Create Minimal Skill

This skill creates minimal but functional XLSX files using only Python's standard library when Excel-writing libraries (openpyxl, xlwt, xlsxwriter) are unavailable.

## When to Use

- Standard Excel libraries are not installed or importable
- You need to generate Excel output from CSV or other data sources
- The file needs to be readable by standard Excel applications

## How It Works

An XLSX file is essentially a ZIP archive containing XML files. This skill constructs:
1. `xl/workbook.xml` - Contains sheet definitions and cell data
2. `_rels/.rels` - Relationship manifest

## Usage Example

```python
import csv
import zipfile
from io import BytesIO
import xml.etree.ElementTree as ET

def create_xlsx(rows, output_path):
    """Create a minimal XLSX file from rows of data"""
    
    # Create the workbook XML
    wb = ET.Element('workbook')
    wb.set('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}xmlns', 
             'http://schemas.openxmlformats.org/spreadsheetml/2006/main')
    
    # Add styles and sheet references
    styleSheet = ET.SubElement(wb, '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}styleSheet')
    workbookPr = ET.SubElement(styleSheet, '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}workbookPr')
    
    # Add sheet
    sheet = ET.SubElement(wb, '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet')
    sheet.set('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}name', 'Sheet1')
    
    # Add sheet data
    sheetData = ET.SubElement(sheet, '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheetData')
    
    for i, row in enumerate(rows):
        rowEl = ET.SubElement(sheetData, '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')
        rowEl.set('r', str(i + 1))
        
        for j, cell in enumerate(row):
            if cell:
                c = ET.SubElement(rowEl, '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c')
                c.set('r', f'AT{ord("A") + j}')
                v = ET.SubElement(c, '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                v.text = str(cell)
    
    # Create the package
    output = BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        # Add xl/workbook.xml
        wb_xml = ET.tostring(wb, encoding='utf-8')
        zf.writestr('xl/workbook.xml', wb_xml)
        
        # Add _rels/.rels
        rels = ET.Element('rels')
        rels.set('{http://schemas.openxmlformats.org/package/2006/relationships}xmlns', 
                   'http://schemas.openxmlformats.org/package/2006/relationships')
        relationship = ET.SubElement(rels, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship')
        relationship.set('Id', 'rId1')
        relationship.set('{http://schemas.openxmlformats.org/package/2006/relationships}Type', 
                         'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument')
        relationship.set('{http://schemas.openxmlformats.org/package/2006/relationships}Target', '/xl/workbook.xml')
        zf.writestr('_rels/.rels', ET.tostring(rels, encoding='utf-8'))
    
    with open(output_path, 'wb') as f:
        f.write(output.getvalue())

# Example usage:
import csv

# Read and filter data
with open('input.csv', 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    rows = list(reader)

filtered_rows = [row for row in rows if '@trevello.com' not in row[4]]

create_xlsx(filtered_rows, 'output.xlsx')
```

## Limitations

- Creates files with a single sheet named "Sheet1"
- Does not support complex formatting (colors, fonts, borders)
- Does not support formulas or functions
- Cell references use simple A1 notation
- Works best for data export scenarios

## Alternative Approaches

If this skill doesn't meet your needs, consider:
1. Installing openpyxl/xlwt via pip in the environment
2. Using the read-xlsx skill which has more comprehensive tools
3. Exporting to CSV and letting the user convert with their own tools