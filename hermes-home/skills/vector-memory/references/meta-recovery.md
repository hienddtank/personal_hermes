# Meta JSON Recovery Procedure

## Problem
`meta_long.json` (or any `meta_*.json`) gets truncated during write, leaving an incomplete last entry. Symptoms:

```
json.decoder.JSONDecodeError: Expecting ',' delimiter: line 2951 column 286 (char 140411)
```

This happens when the daily embed pipeline is killed mid-write (OOM, cron timeout, container restart).

## Cause
The `_save_index()` method in engine.py writes JSON with `json.dump(meta, f, indent=2)`. If the process exits between writing an entry and closing the file, the JSON is invalid.

## Recovery Script

Run from `/workspace/embedding_engine/`:

```python
import json, re

with open('meta_long.json') as f:
    raw = f.read()

# Find entries array
entries_match = re.search(r'"entries"\s*:\s*\[', raw)
if not entries_match:
    print("No entries array found — file may have different structure")
    exit(1)

entries_start = entries_match.end()
entries = []
i = entries_start

while i < len(raw):
    # Skip whitespace and commas between entries
    while i < len(raw) and raw[i] in ' \t\n\r,':
        i += 1
    if i >= len(raw) or raw[i] != '{':
        break

    # Brace-balanced scan for this entry
    depth, in_string, escape_next, start = 0, False, False, i
    for j in range(i, len(raw)):
        c = raw[j]
        if escape_next:
            escape_next = False
            continue
        if c == '\\' and in_string:
            escape_next = True
            continue
        if c == '"' and not escape_next:
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                # Try to parse this entry
                try:
                    entry = json.loads(raw[start:j+1])
                    entries.append(entry)
                except json.JSONDecodeError as e:
                    print(f"Skipping corrupted entry at pos {start}: {e.msg}")
                i = j + 1
                break
    else:
        # Reached EOF without closing brace — last entry is truncated
        print(f"Dropping truncated entry starting at pos {start}")
        print(f"  Preview: {raw[start:start+100].strip()[:80]}...")
        break

# Save recovered data
clean = {
    "entries": entries,
    "version": 1,
    "created_at": 1700000000
}

with open('meta_long.json', 'w') as f:
    json.dump(clean, f, indent=2)

print(f"Recovered {len(entries)} valid entries")
```

## Prevention
- Consider wrapping `_save_meta` in a temp-file + rename pattern: write to `meta_long.json.tmp`, then `os.rename()` to atomically replace.
- Add a `try/except` around `json.load(f)` in `_load_meta` with automatic recovery fallback.

## Related
The same procedure works for `meta_short.json` and `meta_documents.json` — just change the filename.
