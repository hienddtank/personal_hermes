# Mojibake / U+FFFD Replacement Character Handling

When a CSV file contains `�` (replacement character U+FFFD) in text fields, the data went through an encoding conversion where invalid UTF-8 bytes were replaced with the Unicode replacement character. Common causes:

1. **cp1252 → UTF-8 double decode**: File originally in Windows-1252 (Latin-1), opened as UTF-8, then saved with errors='replace'
2. **Mixed encoding sources**: Names from different systems (German CRM + Brazilian spreadsheet) merged without canonicalization

## Diagnosis Steps

1. Read file in **binary mode** (`'rb'`)
2. Search for `\xef\xbf\xbd` (UTF-8 bytes of U+FFFD)
3. Show context around each hit to infer original character
4. Use email addresses, name patterns, and cultural context as clues

## Fix Strategy

Work at the **raw byte level** using `bytes.replace()`. Construct target bytes using UTF-8 encoding:

```python
# German ü = U+00FC → b'\xc3\xbc' in UTF-8
new_raw = raw.replace(b'M\xef\xbf\xbdlle', b'M\xc3\xbcller')

# Portuguese ão = U+00E3 U+006F → b'\xc3\xa3o' in UTF-8
new_raw = new_raw.replace(b'Bar\xef\xbf\xbdo', b'Bar\xc3\xa3o')
```

## Reference Patterns (from real data)

| Original | Context | UTF-8 bytes for replacement char position |
|----------|---------|-------------------------------------------|
| Tainá/Taina | Brazilian Portuguese name | `b'Tain\xef\xbf\xbd'` → `b'Taina'` |
| Müller | German surname | `b'M\xef\xbf\xbdller'` → `b'M\xc3\xbcller'` |
| Barão | Portuguese title/name | `b'Bar\xef\xbf\xbdo'` → `b'Bar\xc3\xa3o'` |
| Françoise | French female name | `b'Fran\xef\xbf\xbdoise'` → `b'Fran\xc3\xa7oise'` |
| Ludmila | Slavic name (no accent) | `b'Lud\xef\xbf\xbdmila'` → `b'Ludmila'` |
| Taise | Japanese name | `b'Ta\xef\xbf\xbdsе'` → `b'Taise'` |

## Prevention

When receiving CSVs from external sources:
- Always try decoding as both `'utf-8'` and `'latin-1'`/`'cp1252'`
- Check for `\xef\xbf\xbd` bytes before parsing with pandas/csv
- If the file has a `.xls` or Excel source, open in Python via `openpyxl` (binary parser, not text) instead of reading as raw CSV
